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
from flask.ext.login import current_user
from flask import send_file

from sqlalchemy import and_

from models import UDI
from models import get_db_session_logger
from models import Preferences
from models import InstallJobHistory
from models import InstallJob
from models import SystemOption

from context import ConnectionContext
from context import InventoryContext
from context import InstallContext

from constants import InstallAction
from constants import get_log_directory
from constants import get_doc_central_directory
from constants import JobStatus

from common import get_last_completed_install_job_for_install_action

from utils import get_file_list
from utils import generate_file_diff
from utils import get_file_timestamp
from utils import multiple_replace
from utils import get_software_platform
from utils import get_software_version
from utils import make_file_writable

from filters import get_datetime_string

from parsers.loader import get_package_parser_class
from csmpe import CSMPluginManager

import os
import re
import shutil
import condoor
import json
import requests
import datetime

class BaseHandler(object):
    def execute(self, ctx):
        try:
            self.start(ctx)
            self.post_processing(ctx)
        except Exception:
            # If there is no db_session, it is not important to log the exception
            if isinstance(ctx, ConnectionContext):
                logger = get_db_session_logger(ctx.db_session)
                logger.exception('BaseHandler.execute() hit exception - hostname = %s', ctx.hostname)
        finally:
            # Remove the server repository password regardless whether the install job is successful or not
            if isinstance(ctx, InstallContext) and (ctx.requested_action == InstallAction.INSTALL_ADD or
                                                    ctx.requested_action == InstallAction.PRE_MIGRATE):
                server_repository_url = ctx.server_repository_url
                if server_repository_url:
                    if server_repository_url.startswith("ftp://"):
                        self.remove_server_repository_password_from_log_files(ctx)
                    # For Pre-Migrate, sftp upload is done differently, no password mangling needed
                    elif server_repository_url.startswith("sftp://") and ctx.requested_action == InstallAction.INSTALL_ADD:
                        self.remove_server_repository_password_from_log_files(ctx)

    def start(self, ctx):
        raise NotImplementedError("Children must override execute")

    def post_processing(self, ctx):
        if isinstance(ctx, ConnectionContext):
            self.update_device_info(ctx)

        if isinstance(ctx, InventoryContext) or isinstance(ctx, InstallContext):
            self.get_software(ctx)

        if isinstance(ctx, InstallContext):
            try:
                if ctx.requested_action == InstallAction.POST_UPGRADE:
                    self.generate_post_upgrade_file_diff(ctx)
                    print "context ctx"
                    print ctx
                    system_option = SystemOption.get(ctx.db_session)
                    print system_option.doc_central_path is not None
                    print ctx.install_job.status
                    if ctx.install_job.status != JobStatus.FAILED and system_option.doc_central_path is not None:
                        self.aggregate_and_upload_logs(ctx)
                elif ctx.requested_action == InstallAction.MIGRATE_SYSTEM or \
                     ctx.requested_action == InstallAction.POST_MIGRATE:
                    self.generate_post_migrate_file_diff(ctx)
                elif ctx.requested_action == InstallAction.PRE_UPGRADE:
                    print "pre-upgrade load data check"
                    print ctx.host.software_version
                    ctx.install_job.save_data("from_release", ctx.host.software_version)
            except Exception:
                logger = get_db_session_logger(ctx.db_session)

                if ctx.requested_action == InstallAction.POST_UPGRADE:
                    msg = 'generate_post_upgrade_file_diff hit exception.'
                else:
                    msg = 'generate_post_migrate_file_diff hit exception.'
                logger.exception(msg)

    def remove_server_repository_password_from_log_files(self, ctx):
        self.remove_server_repository_password_from_log_file(ctx, filename='condoor.log')
        self.remove_server_repository_password_from_log_file(ctx, filename='session.log')

    def remove_server_repository_password_from_log_file(self, ctx, filename):
        in_file = os.path.join(ctx.log_directory, filename)
        out_file = in_file + '.bak'

        try:
            password_pattern = re.compile("ftp://(.*):(?P<PASSWORD>(.*))@")
            with open(in_file) as infile, open(out_file, 'w') as outfile:
                for line in infile:
                    if 'ftp' in line:
                        result = re.search(password_pattern, line)
                        if result:
                            password = result.group("PASSWORD")
                            mangled_password = ('*' * (len(password)))
                            line = line.replace(password, mangled_password)

                    outfile.write(line)

            shutil.move(out_file, in_file)
        except Exception:
            logger = get_db_session_logger(ctx.db_session)
            logger.exception('remove_server_repository_password_from_session_log hit exception.')

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

        return package_parser.get_packages_from_cli(ctx)

    def generate_post_upgrade_file_diff(self, ctx):
        install_job = get_last_completed_install_job_for_install_action(ctx.db_session, ctx.host.id, InstallAction.PRE_UPGRADE)
        if install_job is None:
            return

        self.generate_file_diff(source_file_directory=os.path.join(get_log_directory(), install_job.session_log),
                                target_file_directory=ctx.log_directory)

    def generate_post_migrate_file_diff(self, ctx):
        install_job = get_last_completed_install_job_for_install_action(ctx.db_session, ctx.host.id, InstallAction.PRE_MIGRATE)
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

    def aggregate_and_upload_logs(self, ctx):
        chain = self.get_dependency_chain(ctx.db_session, ctx.install_job.id)

        output_dir = get_doc_central_directory()

        filename_template = "%s_%s_%s-to-%s-%s.txt"
        platform = ctx.host.software_platform
        hostname = ctx.host.hostname
        from_release = "na" if not ctx.install_job.load_data("from_release") else ctx.install_job.load_data("from_release")
        to_release = ctx.host.software_version
        timestamp = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d")
        filename = filename_template %(platform, hostname, from_release, to_release, timestamp)
        print filename
        ctx.install_job.save_data('doc_central_log_file_path', filename)
        # "<software_platform>-<CSM hostname>-<from release>- to - <to release>.<time stamp>.txt"
        output_file = os.path.join(get_doc_central_directory(), filename)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir, 0777)

        with open(output_file, 'w') as outfile:
            for job_id in chain:
                job = ctx.db_session.query(InstallJobHistory).filter(InstallJobHistory.install_job_id == job_id).first()
                if job is None:
                    # Post-Upgrade jobs will not have moved to history table until after this runs
                    job = ctx.db_session.query(InstallJob).filter(InstallJob.id == job_id).first()
                log_directory = os.path.join(get_log_directory(), job.session_log)
                job_logs = os.listdir(log_directory)
                for log in job_logs:
                    if ('.txt' in log or '.log' in log) and log not in ['plugins.log', 'condoor.log'] and '.html' not in log:
                        with open(os.path.join(log_directory, log)) as f:
                            outfile.write("#####################################\n")
                            outfile.write("### %s: %s ###\n" % (job.install_action, log))
                            outfile.write("#####################################\n")
                            outfile.write(f.read())
                            outfile.write("\n\n")

        make_file_writable(output_file)
        return send_file(output_file, as_attachment=True)
        #doc_central_url = "https://docs-services.cisco.com/docservices/upload"
        # url =  "https://docs-services-stg.cisco.com/docservices/upload"

        #preferences = Preferences.get(ctx.db_session, ctx.install_job.id)
        #username = preferences.cco_username
        #password = preferences.cco_password

        #headers = {'userid': username,
        #           'password': password
        #           }

        #system_option = SystemOption.get(ctx.db_session)
        #path = system_option.doc_central_path + '/' + to_release

        #metadata = {
        #    "fileName": output_file,
        #    "title": "CSM Log File",
        #    "description": "CSM Log File",
        #    "docType": "Cisco Engineering Document",
        #    "securityLevel": " ",
        #    "theatre": " ",
        #    "status": " ",
        #    "parent": path
        #}

        #doc_central_url = doc_central_url + "?metadata=" + json.dumps(metadata)

        #files = {'file': open(output_file, 'rb')}

        #resp = requests.post(doc_central_url, headers=headers, files=files)

        #print "Status Code:", resp.status_code
        #print "Headers:", resp.headers
        #print
        #print resp.content

        #return
        #return jsonify(**{ENVELOPE: {'dependency_chain': str(chain)}})

    def get_dependency_chain(self, db_session, install_id):
        install_job = db_session.query(InstallJob).filter(InstallJob.id == install_id).first()
        if install_job is None:
            return

        dependencies = []
        jobs = db_session.query(InstallJobHistory).filter(and_(InstallJobHistory.scheduled_time == install_job.scheduled_time, InstallJobHistory.host_id == install_job.host_id)).all()
        for job in jobs:
            dependencies.append(job.install_job_id)

        dependencies.append(install_id)
        return dependencies
        #dependencies = [install_id]

        #install_job = db_session.query(InstallJobHistory).filter(InstallJobHistory.id == install_id).first()
        #if install_job is None:
        #    install_job = db_session.query(InstallJob).filter(InstallJob.id == install_id).first()
        #if install_job is None:
        #    return
        #if install_job.dependency:
        #    #dependencies.append(install_job.dependency)
        #    dependencies = self.get_dependency_chain(db_session, install_job.dependency) + dependencies

        #return dependencies


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
        pm = CSMPluginManager(ctx)

        try:
            pm.dispatch("run")
        except condoor.GeneralError as e:
            logger = get_db_session_logger(ctx.db_session)
            logger.exception('BaseInventoryHandler hit exception')


class BaseInstallHandler(BaseHandler):
    def start(self, ctx):
        pm = CSMPluginManager(ctx)
        try:
            pm.dispatch("run")
        except condoor.GeneralError as e:
            logger = get_db_session_logger(ctx.db_session)
            logger.exception(e.message)
