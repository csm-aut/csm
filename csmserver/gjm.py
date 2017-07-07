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
from sqlalchemy import or_
from database import DBSession
from models import logger
from models import EmailJob
from models import CreateTarJob
from models import ConvertConfigJob
from models import BackupJob

from multi_process import JobManager
from work_units.email_work_unit import EmailWorkUnit
from work_units.create_tar_work_unit import CreateTarWorkUnit
from work_units.convert_config_work_unit import ConvertConfigWorkUnit
from work_units.backup_work_unit import BackupWorkUnit

from constants import JobStatus


class GenericJobManager(JobManager):
    def __init__(self, num_workers, worker_name):
        JobManager.__init__(self, num_workers=num_workers, worker_name=worker_name)

    def dispatch(self):
        db_session = DBSession()

        self.handle_email_jobs(db_session)
        self.handle_create_tar_jobs(db_session)
        self.handle_convert_config_jobs(db_session)
        self.handle_backup_job(db_session)

        db_session.close()

    def handle_email_jobs(self, db_session):
        try:
            # Include in-progress job in case CSM Server was restarted while the job was in-progress.
            email_jobs = db_session.query(EmailJob).filter(
                or_(EmailJob.status == JobStatus.SCHEDULED, EmailJob.status == JobStatus.IN_PROGRESS)).all()

            if email_jobs:
                for email_job in email_jobs:
                    self.submit_job(EmailWorkUnit(email_job.id))
        except Exception:
            logger.exception('Unable to dispatch email job')

    def handle_create_tar_jobs(self, db_session):
        try:
            # Include in-progress job in case CSM Server was restarted while the job was in-progress.
            create_tar_jobs = db_session.query(CreateTarJob).filter(
                or_(CreateTarJob.status == JobStatus.SCHEDULED, CreateTarJob.status == JobStatus.IN_PROGRESS)).all()

            if create_tar_jobs:
                for create_tar_job in create_tar_jobs:
                    self.submit_job(CreateTarWorkUnit(create_tar_job.id))
        except Exception:
            logger.exception('Unable to dispatch create tar job')

    def handle_convert_config_jobs(self, db_session):
        try:
            # Include in-progress job in case CSM Server was restarted while the job was in-progress.
            convert_config_jobs = db_session.query(ConvertConfigJob).filter(
                or_(ConvertConfigJob.status == JobStatus.SCHEDULED, ConvertConfigJob.status == JobStatus.IN_PROGRESS)
            ).all()

            if convert_config_jobs:
                for convert_config_job in convert_config_jobs:
                    self.submit_job(ConvertConfigWorkUnit(convert_config_job.id))
        except Exception:
            logger.exception('Unable to dispatch convert config job')

    def handle_backup_job(self, db_session):
        try:
            # Include in-progress job in case CSM Server was restarted while the job was in-progress.
            # There should only be one system wide backup job.
            backup_job = db_session.query(BackupJob).filter(
                or_(BackupJob.status == JobStatus.SCHEDULED, BackupJob.status == JobStatus.IN_PROGRESS)).first()

            if backup_job:
                self.submit_job(BackupWorkUnit(backup_job.id))
        except Exception:
            logger.exception('Unable to dispatch backup job')