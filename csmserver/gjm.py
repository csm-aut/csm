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
from database import DBSession
from models import logger
from models import EmailJob, CreateTarJob, ConvertConfigJob

from multi_process import JobManager
from work_units.email_work_unit import EmailWorkUnit
from work_units.create_tar_work_unit import CreateTarWorkUnit
from work_units.convert_config_work_unit import ConvertConfigWorkUnit

from constants import JobStatus


class GenericJobManager(JobManager):
    def __init__(self, num_workers, worker_name):
        JobManager.__init__(self, num_workers=num_workers, worker_name=worker_name)

    def dispatch(self):
        db_session = DBSession()

        self.handle_email_jobs(db_session)
        self.handle_create_tar_jobs(db_session)
        self.handle_convert_config_jobs(db_session)

        db_session.close()

    def handle_email_jobs(self, db_session):
        try:
            # Submit email notification jobs if any
            email_jobs = db_session.query(EmailJob).filter(EmailJob.status == None).all()
            if email_jobs:
                for email_job in email_jobs:
                    self.submit_job(EmailWorkUnit(email_job.id))
        except Exception:
            logger.exception('Unable to dispatch email job')

    def handle_create_tar_jobs(self, db_session):
        try:
            create_tar_jobs = db_session.query(CreateTarJob).filter().all()
            if create_tar_jobs:
                for create_tar_job in create_tar_jobs:
                    if create_tar_job.status != JobStatus.COMPLETED and create_tar_job.status != JobStatus.FAILED:
                        self.submit_job(CreateTarWorkUnit(create_tar_job.id))
        except Exception:
            logger.exception('Unable to dispatch create tar job')

    def handle_convert_config_jobs(self, db_session):
        try:
            convert_config_jobs = db_session.query(ConvertConfigJob).filter().all()
            if convert_config_jobs:
                for convert_config_job in convert_config_jobs:
                    if convert_config_job.status != JobStatus.COMPLETED and \
                       convert_config_job.status != JobStatus.FAILED:
                        self.submit_job(ConvertConfigWorkUnit(convert_config_job.id))
        except Exception:
            logger.exception('Unable to dispatch convert config job')
