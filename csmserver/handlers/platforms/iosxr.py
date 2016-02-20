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

from base import BaseHandler
from parsers.loader import get_package_parser_class 

import condoor

try:
    from csmpe import CSMPluginManager
    csmpe_installed = True
except ImportError:
    from horizon.plugin_manager import PluginManager
    csmpe_installed = False

from models import get_db_session_logger

from constants import InstallAction
from constants import get_log_directory

from common import get_last_successful_pre_upgrade_job

from utils import get_file_list
from utils import generate_file_diff

import time
import os
import re


#import logging
#logging.basicConfig(
#        format='%(asctime)-15s %(levelname)8s: %(message)s',
#        level=logging.DEBUG)


class BaseConnectionHandler(BaseHandler):           
    def execute(self, ctx):

        # would be nice to get the hostname in context
        conn = condoor.Connection('host', ctx.host_urls, log_dir=ctx.log_directory)
        try:
            conn.connect()
            ctx.success = True
        except condoor.ConnectionError as e:
            ctx.post_status = e.message

        
class BaseInventoryHandler(BaseHandler):           
    def execute(self, ctx):
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

            self.get_software(
                ctx.host,
                install_inactive_cli=ctx.inactive_cli,
                install_active_cli=ctx.active_cli,
                install_committed_cli=ctx.committed_cli)
            ctx.success = True

        except condoor.GeneralError as e:
            ctx.post_status = e.message

        finally:
            conn.disconnect()

    def get_software(self, host, install_inactive_cli, install_active_cli, install_committed_cli):
        package_parser_class = get_package_parser_class(host.platform)
        package_parser = package_parser_class()
        
        return package_parser.get_packages_from_cli(
            host,
            install_inactive_cli=install_inactive_cli,
            install_active_cli=install_active_cli,
            install_committed_cli=install_committed_cli
        )


class BaseInstallHandler(BaseHandler):                         
    def execute(self, ctx):

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
        finally:
            try:
                if ctx.requested_action == InstallAction.POST_UPGRADE:
                    self.generate_post_upgrade_file_diff(ctx)
            except:
                logger = get_db_session_logger(ctx.db_session)
                logger.exception('generate_post_upgrade_file_diff hit exception.')

    def generate_post_upgrade_file_diff(self, ctx):
        """
        Search for the last Pre-Upgrade job and generate file diffs.
        """
        if not (os.path.isdir(ctx.log_directory)):
            return

        pre_upgrade_job = get_last_successful_pre_upgrade_job(ctx.db_session, ctx.host.id)
        if pre_upgrade_job is None:
            return

        pre_upgrade_file_directory = os.path.join(get_log_directory(), pre_upgrade_job.session_log)
        post_upgrade_file_directory = ctx.log_directory
        pre_upgrade_file_list = get_file_list(pre_upgrade_file_directory)
        post_upgrade_file_list = get_file_list(post_upgrade_file_directory)

        for filename in post_upgrade_file_list:
            if 'POST-UPGRADE' in filename and filename.replace('POST-UPGRADE', 'PRE-UPGRADE') in pre_upgrade_file_list:
                post_upgrade_file_path = os.path.join(post_upgrade_file_directory, filename)
                pre_upgrade_file_path = os.path.join(
                    pre_upgrade_file_directory, filename.replace('POST-UPGRADE', 'PRE-UPGRADE'))

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
                        diff_file_name = os.path.join(post_upgrade_file_directory, filename + '.diff')
                        with open(diff_file_name, 'w') as fo:
                            fo.write(html_code + results)