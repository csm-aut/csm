from sqlalchemy import and_

from handlers.loader import get_inventory_handler_class
from handlers.loader import get_install_handler_class
from base import InstallContext

from utils import create_log_directory
from utils import is_empty

from filters import get_datetime_string

from mailer import create_email_job

from constants import InstallAction
from constants import JobStatus

from multi_process import WorkUnit

from models import Host
from models import InstallJob
from models import InstallJobHistory
from models import SystemOption

import traceback
import datetime
import urllib

class InstallWorkUnit(WorkUnit):
    def __init__(self, host_id, job_id):
        WorkUnit.__init__(self)

        self.host_id = host_id
        self.job_id = job_id

    def get_unique_key(self):
        return self.host_id

    def get_software(self, ctx, logger):
        handler_class = get_inventory_handler_class(ctx.host.platform)
        if handler_class is None:
            logger.error('SoftwareManager: Unable to get handler for %s', ctx.host.platform)

        handler = handler_class()
        if handler.get_software(ctx.host, ctx.inactive_cli, ctx.active_cli, ctx.committed_cli):
            # Update the time stamp
            ctx.host.inventory_job[0].set_status(JobStatus.COMPLETED)

    def start(self, db_session, logger, process_name):
        ctx = None

        # print('processing', process_name, self.host_id, self.in_progress_hosts.__str__() )

        try:
            # print('processing 1', process_name, self.host_id, self.in_progress_hosts.__str__() )
            install_job = db_session.query(InstallJob).filter(InstallJob.id == self.job_id).first()

            # print('processing 1.1', process_name, self.host_id, self.in_progress_hosts.__str__() )
            if install_job is None:
                # print('INSTALL JOB NONE', process_name, self.host_id, self.in_progress_hosts.__str__() )
                # This is normal because of race condition. It means the job is already deleted (completed).
                return

            # print('processing 2', process_name, self.host_id, self.in_progress_hosts.__str__() )
            if not db_session.query(SystemOption).first().can_install:
                # This will halt this host that has already been queued
                # print('CAN INSTALL', process_name, self.host_id, self.in_progress_hosts.__str__() )
                return

            # print('processing 3', process_name, self.host_id, self.in_progress_hosts.__str__() )
            host = db_session.query(Host).filter(Host.id == self.host_id).first()
            if host is None:
                logger.error('Unable to retrieve host %s', self.host_id)
                return

            # print('processing 4', process_name, self.host_id, self.in_progress_hosts.__str__() )
            handler_class = get_install_handler_class(host.platform)
            if handler_class is None:
                logger.error('Unable to get handler for %s, install job %s', host.platform, self.job_id)

            install_job.start_time = datetime.datetime.utcnow()
            install_job.set_status(JobStatus.PROCESSING)
            install_job.session_log = create_log_directory(host.connection_param[0].host_or_ip, install_job.id)

            ctx = InstallContext(db_session, host, install_job)
            ctx.operation_id = self.get_last_operation_id(db_session, install_job)

            # print('processing 5', process_name, self.host_id, self.in_progress_hosts.__str__() )
            db_session.commit()

            # print('processing 6', process_name, self.host_id, self.in_progress_hosts.__str__() )

            handler = handler_class()
            handler.execute(ctx)

            if ctx.success:
                # print('processing 7', process_name, self.host_id, self.in_progress_hosts.__str__() )
                # Update the software
                self.get_software(ctx, logger)
                self.archive_install_job(db_session, logger, ctx, host, install_job, JobStatus.COMPLETED, process_name)
            else:
                # print('processing 8', process_name, self.host_id, self.in_progress_hosts.__str__() )
                self.archive_install_job(db_session, logger, ctx, host, install_job, JobStatus.FAILED, process_name)

        except Exception:
            # print('processing 9', process_name, self.host_id, self.in_progress_hosts.__str__() )
            try:
                logger.exception('InstallManager hit exception - install job =  %s', self.job_id)
                self.archive_install_job(db_session, logger, ctx, host, install_job, JobStatus.FAILED, process_name, trace=traceback.format_exc())
            except Exception:
                logger.exception('InstallManager hit exception - install job = %s', self.job_id)
        finally:
            db_session.close()

        # print('after removing', process_name, self.host_id, self.in_progress_hosts.__str__() )

    def get_last_operation_id(self, db_session, install_activate_job, trace=None):

        if install_activate_job.install_action == InstallAction.INSTALL_ACTIVATE:
            install_add_job = self.get_last_successful_install_job(db_session, install_activate_job.host_id)
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

    def get_last_successful_install_job(self, db_session, host_id):
        return db_session.query(InstallJobHistory). \
            filter((InstallJobHistory.host_id == host_id), and_(InstallJobHistory.install_action == InstallAction.INSTALL_ADD)). \
            order_by(InstallJobHistory.status_time.desc()).first()

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
        # print('before email', process_name, self.host_id, self.in_progress_hosts.__str__() )
        self.create_email_notification(db_session, logger, host, install_job_history)
        # print('after email', process_name, self.host_id, self.in_progress_hosts.__str__() )

    def create_email_notification(self, db_session, logger, host, install_job):
        try:
            session_log_link = "hosts/{}/install_job_history/session_log/{}?file_path={}".format(
                urllib.quote(host.hostname), install_job.id, install_job.session_log)

            message = '<html><head><body>'
            if install_job.status == JobStatus.COMPLETED:
                message += 'The scheduled installation for host "' + host.hostname + '" has COMPLETED<br><br>'
            elif install_job.status == JobStatus.FAILED:
                message += 'The scheduled installation for host "' + host.hostname + '" has FAILED<br><br>'

            message += 'Scheduled Time: ' + get_datetime_string(install_job.scheduled_time) + ' (UTC)<br>'
            message += 'Start Time: ' + get_datetime_string(install_job.start_time) + ' (UTC)<br>'
            message += 'Install Action: ' + install_job.install_action + '<br><br>'

            session_log_url = SystemOption.get(db_session).base_url + '/' + session_log_link

            message += 'For more information, click the link below<br><br>'
            message += session_log_url + '<br><br>'

            if install_job.packages is not None and len(install_job.packages) > 0:
                message += 'Followings are the software packages: <br><br>' + install_job.packages.replace(',','<br>')

            message += '</body></head></html>'

            create_email_job(db_session, logger, message, install_job.created_by)

        except Exception:
            logger.exception('create_email_notification hit exception')

