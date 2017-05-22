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
from handlers.doc_central import handle_doc_central_logging
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
            install_job.set_status(JobStatus.IN_PROGRESS)
            if not install_job.session_log:
                install_job.session_log = create_log_directory(host.connection_param[0].host_or_ip, install_job.id)

            # Reset the job_info field especially for a re-submitted job.
            install_job.save_data('job_info', [])

            db_session.commit()

            handler = handler_class()
            handler.execute(ctx)

            if ctx.success:
                try:
                    # Update the software
                    self.get_inventory(ctx, logger)
                except Exception:
                    pass

                # Support Doc Central feature for SIT team
                if install_job.install_action == InstallAction.PRE_UPGRADE or \
                                install_job.install_action == InstallAction.INSTALL_ADD:
                    install_job.save_data("from_release", ctx.host.software_version)

                self.post_process_complete_install_jobs(db_session, install_job, host, logger)

                # Support Doc Central feature for SIT team - must be done after archive_install_job.
                handle_doc_central_logging(ctx, logger)
            else:
                self.post_process_incomplete_install_jobs(db_session, install_job, host, logger)

        except Exception:
            try:
                self.log_exception(logger, host)
                self.post_process_incomplete_install_jobs(db_session, install_job, host, logger,
                                                          trace=traceback.format_exc())
            except Exception:
                self.log_exception(logger, host)
        finally:
            db_session.close()

    def post_process_complete_install_jobs(self, db_session, install_job, host, logger):
        print "install work unit install job completed"
        self.archive_install_job(db_session, logger, host, install_job, JobStatus.COMPLETED)

    def post_process_incomplete_install_jobs(self, db_session, install_job, host, logger, trace=None):
        print "install work unit install job failed"
        self.archive_install_job(db_session, logger, host, install_job, JobStatus.FAILED, trace=trace)

    def log_exception(self, logger, host):
        logger.exception('InstallManager hit exception - hostname = %s, install job =  %s',
                         host.hostname if host is not None else 'Unknown', self.job_id)

    def archive_install_job(self, db_session, logger, host, install_job, job_status, trace=None):

        install_job_history = InstallJobHistory()
        install_job_history.install_job_id = install_job.id
        install_job_history.host_id = install_job.host_id
        install_job_history.install_action = install_job.install_action
        install_job_history.packages = install_job.packages
        install_job_history.scheduled_time = install_job.scheduled_time
        install_job_history.start_time = install_job.start_time
        install_job_history.set_status(job_status)
        install_job_history.dependency = install_job.dependency
        install_job_history.session_log = install_job.session_log
        install_job_history.created_by = install_job.created_by
        install_job_history.data = install_job.data
        install_job_history.trace = trace

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
            session_log_link = "log/hosts/{}/install_job_history/session_log/{}?file_path={}".format(
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


class InstallPendingMonitoringWorkUnit(InstallWorkUnit):
    """This class contains methods specific for install jobs that upon successful execution,
    need csm to schedule monitor jobs to check the completion of the jobs."""

    def post_process_complete_install_jobs(self, db_session, install_job, host, logger):
        print "install pending monitor work unit install job completed"
        # submit new monitor install jobs
        install_job.set_status(JobStatus.WAITING)
        new_monitor_job = install_job.create_monitor_job()
        if not new_monitor_job:
            logger.exception(
                "Fail to schedule a monitor job for install job id = {}, job action = {}. Archiving this install job as FAILED.".format(
                    install_job.id, install_job.install_action
                ))
            self.archive_install_job(db_session, logger, host, install_job, JobStatus.FAILED)
            return

        time_interval = new_monitor_job.load_data("time_interval")
        install_job.set_status_message(
            "Waiting for first monitor attempt in {} seconds.".format(
                time_interval if time_interval else 'unknown',
            )
        )

        db_session.add(new_monitor_job)
        db_session.commit()


class MonitorWorkUnit(InstallWorkUnit):
    """This class contains methods specific for the monitoring install jobs
    that executes periodically until successful completion or reached maximum
    number of trials."""

    def post_process_complete_install_jobs(self, db_session, monitor_job, host, logger):
        print "monitor work unit install job completed"
        original_install_job = db_session.query(InstallJob).filter(InstallJob.id == monitor_job.dependency).first()

        if original_install_job:
            trial_number = monitor_job.load_data("trial_number")
            max_trials = monitor_job.load_data("max_trials")

            original_install_job.set_status_message(
                "{}/{} monitor attempt. Result: Job completed.".format(
                    trial_number if trial_number else 'unknown',
                    max_trials if max_trials else 'unknown'
                )
            )


        self.archive_original_install_job_based_on_monitor_job(db_session, monitor_job, original_install_job,
                                                               JobStatus.COMPLETED, host, logger)
        db_session.commit()

    def post_process_incomplete_install_jobs(self, db_session, monitor_job, host, logger, trace=None):
        print "monitor work unit install job failed"

        original_install_job = db_session.query(InstallJob).filter(
            InstallJob.id == monitor_job.dependency).first()

        trial_number = monitor_job.load_data("trial_number")
        max_trials = monitor_job.load_data("max_trials")
        time_interval = monitor_job.load_data("time_interval")

        # update the number of trials and status time for this install_job and
        # check if it's still within max number of trials allowed
        if monitor_job.update_and_check_number_of_trials():

            monitor_job.prepare_for_next_execution()

            original_install_job.set_status_message(
                "{}/{} monitor attempt. Result: Job not complete. Waiting for next monitor attempt in {} seconds.".format(
                    trial_number if trial_number else 'unknown',
                    max_trials if max_trials else 'unknown',
                    time_interval if time_interval else 'unknown'
                )
            )

        # if this install_job reached its max number of trials or if the trial info is missing from the install job
        # we will archive the original job with status as FAILED, and delete this install_job
        else:
            original_install_job.set_status_message(
                "{}/{} monitor attempt. Result: Job not complete. Maximum monitor attempts reached.".format(
                    trial_number if trial_number else 'unknown',
                    max_trials if max_trials else 'unknown',
                    time_interval if time_interval else 'unknown'
                )
            )
            self.archive_original_install_job_based_on_monitor_job(db_session, monitor_job, original_install_job,
                                                                   JobStatus.FAILED, host, logger, trace)
        db_session.commit()

    def archive_original_install_job_based_on_monitor_job(self, db_session, monitor_job, original_install_job,
                                                          job_status, host, logger, trace=None):
        if original_install_job:
            self.archive_install_job(db_session, logger, host, original_install_job, job_status, trace=trace)
        else:
            logger.exception(
                "Fail to find the original install job id = {} for monitor job id = {}, job action = {}. Deleting monitor job.".format(
                    monitor_job.dependency, monitor_job.id, monitor_job.install_action
                ))
        db_session.delete(monitor_job)
        db_session.commit()
