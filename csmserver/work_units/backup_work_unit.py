from multi_process import WorkUnit

from database import get_database_settings

from models import BackupJob
from common import get_server_by_id

from datetime import date

from constants import get_backup_directory
from constants import JobStatus

from server_helper import get_server_impl

import os
import subprocess
import calendar


class BackupWorkUnit(WorkUnit):
    def __init__(self, job_id):
        WorkUnit.__init__(self)

        self.job_id = job_id

    def start(self, db_session, logger, process_name):
        backup_job = None
        try:
            backup_job = db_session.query(BackupJob).filter(BackupJob.id == self.job_id).first()
            if backup_job is None:
                logger.error('Unable to retrieve backup job: %s' % self.job_id)
                return

            self.backup_database(db_session, logger, backup_job)
            backup_job.set_status(JobStatus.COMPLETED)
        except Exception as e:
            backup_job.set_status_message(e.message)
            backup_job.set_status(JobStatus.FAILED)
            logger.exception('BackupWorkUnit.start() hit exception.')
        finally:
            db_session.commit()
            db_session.close()

    def backup_database(self, db_session, logger, backup_job):
        db_dict = get_database_settings()

        database = db_dict['database']
        username = db_dict['username']
        password = db_dict['password']

        today = date.today()
        day_of_week = calendar.day_abbr[today.weekday()]
        dest_filename = '{}-{}.sql'.format(database, day_of_week.lower())
        dest_file_path = os.path.join(get_backup_directory(), dest_filename)

        # FIXME: Currently, use hardcoded path
        mysqldump = '/usr/local/mysql/bin/mysqldump'
        if not os.path.isfile(mysqldump):
            mysqldump = '/usr/bin/mysqldump'
            if not os.path.isfile(mysqldump):
                mysqldump = 'mysqldump'

        command = '{} {} -u {} -p{} > {}'.format(mysqldump, database, username, password, dest_file_path)

        exit_code = subprocess.call(command, shell=True)
        if exit_code != 0:
            raise Exception('{}: Unable to backup database.'.format(mysqldump))

        if backup_job.server_id != -1:
            self.upload_file(db_session, backup_job.server_id, backup_job.server_directory, dest_file_path, dest_filename)

    def upload_file(self, db_session, server_id, server_directory, source_file_path, dest_filename):
        server = get_server_by_id(db_session, server_id)
        if server is not None:
            server_impl = get_server_impl(server)
            if server_impl is not None:
                server_impl.upload_file(source_file_path=source_file_path,
                                        dest_filename=dest_filename,
                                        sub_directory=server_directory)
            else:
                raise Exception('No implementation available for server repository = {}'.format(server_id))
        else:
            raise Exception('Unable to locate server repository = {}'.format(server_id))

    def get_unique_key(self):
        return 'backup_job_{}'.format(self.job_id)
