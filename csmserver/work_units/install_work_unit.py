# =============================================================================
# Copyright (c) 2016, Cisco Systems, Inc
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
from handlers.loader import get_inventory_handler_class
from handlers.loader import get_install_handler_class
from context import InstallContext

from utils import create_log_directory
from utils import is_empty
from utils import get_log_directory
from utils import get_file_list

from filters import get_datetime_string

from mailer import create_email_job

from constants import InstallAction
from constants import JobStatus

from multi_process import WorkUnit

from models import Host
from models import InstallJob
from models import InstallJobHistory
from models import SystemOption

from common import get_last_completed_install_job_for_install_action

import traceback
import datetime
import urllib
import os


class InstallWorkUnit(WorkUnit):
    def __init__(self, host_id, job_id):
        WorkUnit.__init__(self)

        self.host_id = host_id
        self.job_id = job_id

    def get_unique_key(self):
        return self.host_id

    def get_inventory(self, ctx, logger):
        handler_class = get_inventory_handler_class(ctx)
        if handler_class is None:
            logger.error('SoftwareManager: Unable to get handler for %s', ctx.host.software_platform)

        handler = handler_class()
        if handler.get_inventory(ctx):
            # Update the time stamp
            ctx.host.inventory_job[0].set_status(JobStatus.COMPLETED)

    def start(self, db_session, logger, process_name):
        ctx = None
        host = None
        try:
            install_job = db_session.query(InstallJob).filter(InstallJob.id == self.job_id).first()

            if install_job is None:
                # This is normal because of race condition. It means the job is already deleted (completed).
                return

            if not db_session.query(SystemOption).first().can_install:
                # This will halt this host that has already been queued
                return

            host = db_session.query(Host).filter(Host.id == self.host_id).first()
            if host is None:
                logger.error('Unable to retrieve host %s', self.host_id)
                return

            ctx = InstallContext(db_session, host, install_job)

            handler_class = get_install_handler_class(ctx)
            if handler_class is None:
                logger.error('Unable to get handler for %s, install job %s', host.software_platform, self.job_id)

            install_job.start_time = datetime.datetime.utcnow()
            install_job.set_status(JobStatus.PROCESSING)
            install_job.session_log = create_log_directory(host.connection_param[0].host_or_ip, install_job.id)

            ctx.operation_id = self.get_last_operation_id(db_session, install_job)

            db_session.commit()

            handler = handler_class()
            handler.execute(ctx)

            if ctx.success:
                try:
                    # Update the software
                    self.get_inventory(ctx, logger)
                except Exception:
                    pass
                self.archive_install_job(db_session, logger, ctx, host, install_job, JobStatus.COMPLETED, process_name)
            else:
                self.archive_install_job(db_session, logger, ctx, host, install_job, JobStatus.FAILED, process_name)

        except Exception:
            try:
                self.log_exception(logger, host)
                self.archive_install_job(db_session, logger, ctx, host, install_job,
                                         JobStatus.FAILED, process_name, trace=traceback.format_exc())
            except Exception:
                self.log_exception(logger, host)
        finally:
            db_session.close()

    def log_exception(self, logger, host):
        logger.exception('InstallManager hit exception - hostname = %s, install job =  %s',
                         host.hostname if host is not None else 'Unknown', self.job_id)

    def get_last_operation_id(self, db_session, install_activate_job, trace=None):

        if install_activate_job.install_action == InstallAction.INSTALL_ACTIVATE:
            install_add_job = get_last_completed_install_job_for_install_action(db_session,
                                                                                install_activate_job.host_id,
                                                                                InstallAction.INSTALL_ADD)
            if install_add_job is not None:
                # Check if Last Install Add and Activate have the same packages.
                # If they have, then return the operation id.
                install_add_packages = install_add_job.packages.split(',') if not is_empty(install_add_job.packages) else []
                install_activate_packages = install_activate_job.packages.split(',') if not is_empty(install_activate_job.packages) else []
                if len(install_add_packages) == len(install_activate_packages):
                    for install_activate_package in install_activate_packages:
                        if install_activate_package not in install_add_packages:
                            return -1
                    return install_add_job.operation_id

        return -1

    def archive_install_job(self, db_session, logger, ctx, host, install_job, job_status, process_name, trace=None):

        install_job_history = InstallJobHistory()
        install_job_history.install_job_id = install_job.id
        install_job_history.host_id = install_job.host_id
        install_job_history.install_action = install_job.install_action
        install_job_history.packages = install_job.packages
        install_job_history.scheduled_time = install_job.scheduled_time
        install_job_history.start_time = install_job.start_time
        install_job_history.set_status(job_status)
        install_job_history.session_log = install_job.session_log
        install_job_history.created_by = install_job.created_by
        install_job_history.trace = trace

        if ctx is not None:
            install_job_history.operation_id = ctx.operation_id

        # Only delete the install job if it is completed successfully.
        # Failed job should still be retained in the InstallJob table.
        if job_status == JobStatus.COMPLETED:
            db_session.delete(install_job)
        else:
            install_job.set_status(job_status)
            if trace is not None:
                install_job.trace = trace

        db_session.add(install_job_history)
        db_session.commit()

        # Send notification error
        self.create_email_notification(db_session, logger, host, install_job_history)

    def create_email_notification(self, db_session, logger, host, install_job):
        try:
            session_log_link = "hosts/{}/install_job_history/session_log/{}?file_path={}".format(
                urllib.quote(host.hostname), install_job.id, install_job.session_log)

            message = '<html><head></head><body>'
            if install_job.status == JobStatus.COMPLETED:
                message += 'The scheduled installation for host "' + host.hostname + '" has COMPLETED.<br><br>'
            elif install_job.status == JobStatus.FAILED:
                message += 'The scheduled installation for host "' + host.hostname + '" has FAILED.<br><br>'

            message += 'Scheduled Time: ' + \
                       get_datetime_string(install_job.scheduled_time) + \
                       ' UTC<br>'
            message += 'Start Time: ' + \
                       get_datetime_string(install_job.start_time) + \
                       ' UTC<br>'
            message += 'Install Action: ' + install_job.install_action + '<br><br>'

            message = self.check_command_file_diff(install_job, message)

            session_log_url = SystemOption.get(db_session).base_url + '/' + session_log_link

            message += 'For more information, click the link below<br><br>'
            message += session_log_url + '<br><br>'

            if install_job.packages is not None and len(install_job.packages) > 0:
                message += 'Followings are the software packages: <br><br>' + install_job.packages.replace(',','<br>')

            message += '</body></html>'

            create_email_job(db_session, logger, message, install_job.created_by)

        except Exception:
            logger.exception('create_email_notification() hit exception')

    def check_command_file_diff(self, install_job, message):
        file_suffix = '.diff.html'
        file_list = get_file_list(os.path.join(get_log_directory(), install_job.session_log))
        diff_file_list = [file for file in file_list if file_suffix in file]

        if len(diff_file_list) > 0:
            message += 'The following command outputs have changed between different installation phases<br><br>'
            for file in diff_file_list:
                message += file.replace(file_suffix, '') + '<br>'
            message += '<br>'

        return message
