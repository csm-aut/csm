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
from utils import import_class
from constants import UNKNOWN
from models import UDI
from models import get_db_session_logger

from base import ConnectionContext
from base import InstallContext

from constants import InstallAction
from constants import get_log_directory

from common import get_last_successful_pre_upgrade_job

from utils import get_file_list
from utils import generate_file_diff

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

    def generate_post_upgrade_file_diff(self, ctx):
        """
        Search for the last Pre-Upgrade job and generate file diffs.
        """
        if not (os.path.isdir(ctx.log_directory)):
            return

        pre_upgrade_job = get_last_successful_pre_upgrade_job(ctx.db_session, ctx.host.id)
        if pre_upgrade_job is None:
            return

        source_file_directory = os.path.join(get_log_directory(), pre_upgrade_job.session_log)
        target_file_directory = ctx.log_directory

        self.generate_file_diff(source_string='PRE-UPGRADE',
                                target_string='POST-UPGRADE',
                                source_file_directory=source_file_directory,
                                target_file_directory=target_file_directory)

    def generate_file_diff(self, source_string, target_string, source_file_directory, target_file_directory):
        source_file_list = get_file_list(source_file_directory)
        target_file_list = get_file_list(target_file_directory)

        for filename in target_file_list:
            if target_string in filename and filename.replace(target_string, source_string) in source_file_list:
                post_upgrade_file_path = os.path.join(target_file_directory, filename)
                pre_upgrade_file_path = os.path.join(
                    source_file_directory, filename.replace(target_string, source_string))

                if os.path.isfile(pre_upgrade_file_path) and os.path.isfile(post_upgrade_file_path):
                    results = generate_file_diff(pre_upgrade_file_path, post_upgrade_file_path)
                    # Are there any changes in the logs
                    insertion_count = results.count('ins style')
                    deletion_count = results.count('del style')

                    if insertion_count > 0 or deletion_count > 0:
                        results = results.replace(' ', '&nbsp;')

                        # Performs a one-pass replacements
                        rep = {"ins&nbsp;style": "ins style", "del&nbsp;style": "del style", "&para;": ''}
                        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
                        pattern = re.compile("|".join(rep.keys()))
                        results = pattern.sub(lambda m: rep[re.escape(m.group(0))], results)

                        # Add insertion and deletion status
                        html_code = '<ins style="background:#e6ffe6;">Insertions</ins>:&nbsp;' + str(insertion_count) + \
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


def discover_platform_info(ctx):
    conn = condoor.Connection(ctx.hostname, ctx.host_urls)

    try:
        conn.discovery()
        ctx.host.family = conn.family
        ctx.host.platform = conn.platform
        ctx.host.software_platform = get_software_platform(family=conn.family, os_type=conn.os_type)
        ctx.host.software_version = get_software_version(conn.os_version)
        ctx.host.os_type = conn.os_type
        ctx.db_session.commit()
    except condoor.ConnectionError as e:
        pass
    finally:
        conn.disconnect()


def get_software_platform(family, os_type):
    if family == 'ASR9K' and os_type == 'eXR':
        return 'ASR9K-64b'
    else:
        return family


def get_software_version(version):
    # Strip all characters after '[' (i.e., 5.3.2[Default])
    head, sep, tail = version.partition('[')
    return head


def get_connection_handler():
    return BaseConnectionHandler()


def get_inventory_handler_class(ctx):
    if ctx.host.family == UNKNOWN:
        discover_platform_info(ctx)

    return import_class('handlers.platforms.%s.InventoryHandler' % ctx.host.software_platform)


def get_install_handler_class(ctx):
    if ctx.host.family == UNKNOWN:
        discover_platform_info(ctx)

    return import_class('handlers.platforms.%s.InstallHandler' % ctx.host.software_platform)

