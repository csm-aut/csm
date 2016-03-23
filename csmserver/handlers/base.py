# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
# =============================================================================
from models import UDI
from models import get_db_session_logger

from context import ConnectionContext
from context import SoftwareContext
from context import InstallContext

from constants import PlatformFamily
from constants import InstallAction
from constants import get_log_directory

from common import get_last_successful_pre_upgrade_job

from utils import get_file_list
from utils import generate_file_diff
from utils import get_file_timestamp
from utils import multiple_replace
from filters import get_datetime_string

from parsers.loader import get_package_parser_class


try:
    from csmpe import CSMPluginManager
    csmpe_installed = True
except ImportError:
    from horizon.plugin_manager import PluginManager
    csmpe_installed = False

import re
import os
import condoor

class BaseHandler(object):
    def execute(self, ctx):
        try:
            self.start(ctx)
            self.post_processing(ctx)
        except Exception:
            # If there is no db_session, it is not important to log the exception
            if isinstance(ctx, ConnectionContext):
                logger = get_db_session_logger(ctx.db_session)
                logger.exception('execute() hit exception.')

    def start(self, ctx):
        raise NotImplementedError("Children must override execute")

    def post_processing(self, ctx):
        if isinstance(ctx, ConnectionContext):
            self.update_device_info(ctx)

        if isinstance(ctx, SoftwareContext):
            self.get_software(ctx)

        if isinstance(ctx, InstallContext):
            try:
                if ctx.requested_action == InstallAction.POST_UPGRADE:
                    self.generate_post_upgrade_file_diff(ctx)
            except Exception:
                logger = get_db_session_logger(ctx.db_session)
                logger.exception('generate_post_upgrade_file_diff hit exception.')


    def update_device_info(self, ctx):
        device_info_dict = ctx.load_data('device_info')
        if device_info_dict is not None:
            ctx.host.family = device_info_dict['family']
            ctx.host.platform = device_info_dict['platform']
            ctx.host.software_platform = get_software_platform(family=device_info_dict['family'],
                                                               os_type=device_info_dict['os_type'])
            ctx.host.software_version = get_software_version(device_info_dict['os_version'])
            ctx.host.os_type = device_info_dict['os_type']

        udi_dict = ctx.load_data('udi')
        if udi_dict is not None:
            udi = UDI(name=udi_dict['name'], description=udi_dict['description'],
                      pid=udi_dict['pid'], vid=udi_dict['vid'], sn=udi_dict['sn'])
            ctx.host.UDIs = [udi]


    def get_software(self, ctx):
        package_parser_class = get_package_parser_class(ctx.host.software_platform)
        package_parser = package_parser_class()

        return package_parser.get_packages_from_cli(
            ctx.host,
            install_inactive_cli=ctx.inactive_cli,
            install_active_cli=ctx.active_cli,
            install_committed_cli=ctx.committed_cli
        )

    def generate_post_upgrade_file_diff(self, ctx):
        install_job = get_last_successful_pre_upgrade_job(ctx.db_session, ctx.host.id)
        if install_job is None:
            return

        self.generate_file_diff(source_file_directory=os.path.join(get_log_directory(), install_job.session_log),
                                target_file_directory=ctx.log_directory)

    def generate_file_diff(self, source_file_directory, target_file_directory):
        source_file_list = get_file_list(source_file_directory)
        target_file_list = get_file_list(target_file_directory)

        for filename in target_file_list:
            if '.txt' in filename and filename in source_file_list:
                target_file_path = os.path.join(target_file_directory, filename)
                source_file_path = os.path.join(source_file_directory, filename)

                if os.path.isfile(source_file_path) and os.path.isfile(target_file_path):
                    results = generate_file_diff(source_file_path, target_file_path)
                    # Are there any changes in the logs
                    insertion_count = results.count('ins style')
                    deletion_count = results.count('del style')

                    if insertion_count > 0 or deletion_count > 0:
                        results = results.replace(' ', '&nbsp;')

                        rep_dict = {"ins&nbsp;style": "ins style", "del&nbsp;style": "del style", "&para;": ''}
                        results = multiple_replace(results, rep_dict)

                        source_filename = 'File 1: ' + filename + ' (created on ' + \
                                          get_datetime_string(get_file_timestamp(source_file_path)) + ')'
                        target_filename = 'File 2: ' + filename + ' (created on ' + \
                                          get_datetime_string(get_file_timestamp(target_file_path)) + ')'

                        # Add insertion and deletion status
                        html_code = source_filename + '<br>' + target_filename + '<br><br>' + \
                                    '<ins style="background:#e6ffe6;">Insertions</ins>:&nbsp;' + str(insertion_count) + \
                                    '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;' + \
                                    '<del style="background:#ffe6e6;">Deletions</del>:&nbsp;' + str(deletion_count) + \
                                    '<hr>'
                        diff_file_name = os.path.join(target_file_directory, filename + '.diff.html')
                        with open(diff_file_name, 'w') as fo:
                            fo.write('<pre>' + html_code + results + '</pre>')


class BaseConnectionHandler(BaseHandler):
    def start(self, ctx):
        conn = condoor.Connection(ctx.hostname, ctx.host_urls)
        try:
            conn.connect()
            ctx.success = True
        except condoor.ConnectionError as e:
            pass


#import logging
#logging.basicConfig(
#        format='%(asctime)-15s %(levelname)8s: %(message)s',
#        level=logging.DEBUG)

class BaseInventoryHandler(BaseHandler):
    def start(self, ctx):
        conn = condoor.Connection(ctx.host.hostname, ctx.host_urls, log_dir=ctx.log_directory)
        try:
            conn.discovery()
        except condoor.GeneralError as e:
            ctx.post_status = e.message
            return

        try:
            conn.connect()

            if conn.os_type == "XR":
                ctx.inactive_cli = conn.send('sh install inactive summary')
                ctx.active_cli = conn.send('sh install active summary')
                ctx.committed_cli = conn.send('sh install committed summary')
            elif conn.os_type == "eXR":
                ctx.inactive_cli = conn.send('sh install inactive')
                ctx.active_cli = conn.send('sh install active')
                ctx.committed_cli = conn.send('sh install committed')

            ctx.success = True

        except condoor.GeneralError as e:
            ctx.post_status = e.message

        finally:
            conn.disconnect()


class BaseInstallHandler(BaseHandler):
    def start(self, ctx):

        if csmpe_installed:
            pm = CSMPluginManager(ctx)
        else:
            pm = PluginManager()
        try:
            if csmpe_installed:
                pm.dispatch("run")
            else:
                pm.run(ctx)
        except condoor.GeneralError as e:
            ctx.post_status = e.message
            ctx.success = False


def get_software_platform(family, os_type):
    if family == PlatformFamily.ASR9K and os_type == 'eXR':
        return PlatformFamily.ASR9K_X64
    else:
        return family


def get_software_version(version):
    # Strip all characters after '[' (i.e., 5.3.2[Default])
    head, sep, tail = version.partition('[')
    return head