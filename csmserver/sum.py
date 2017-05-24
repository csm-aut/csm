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
import datetime

from database import DBSession
from sqlalchemy import or_
from sqlalchemy import and_

from models import InstallJob
from models import InstallJobHistory
from models import SystemOption
from models import get_download_job_key_dict
from models import get_db_session_logger

from constants import JobStatus
from constants import InstallJobType

from multi_process import JobManager
from filters import get_datetime_string

from work_units import install_work_unit


class SoftwareManager(JobManager):
    def __init__(self, num_workers, worker_name):
        JobManager.__init__(self, num_workers=num_workers, worker_name=worker_name)
    
    """
    In order for a scheduled install job to proceed, its dependency must be successfully completed
    and is present in the InstallJobHistory table.  It is possible that the dependency (install_job_id) 
    has multiple entries in the table.  This can happen when it takes multiple tries for the dependency 
    to become successful (i.e. after couple failed attempts).  it is also possible that the install job id
    previously deleted from the install_job table will be re-used by the database.  Thus, there is a need
    to also check the dependency_scheduled_time previously saved in the data field.
    """
    def get_install_job_dependency_completed(self, db_session, install_job):
        install_history_jobs = db_session.query(InstallJobHistory).filter(and_(
                                                InstallJobHistory.install_job_id == install_job.dependency,
                                                InstallJobHistory.host_id == install_job.host_id,
                                                InstallJobHistory.status == JobStatus.COMPLETED)).all()

        if len(install_history_jobs) > 0:
            for install_history_job in install_history_jobs:
                dependency_scheduled_time = install_job.load_data('dependency_scheduled_time')
                if dependency_scheduled_time is not None and \
                        get_datetime_string(install_history_job.scheduled_time) == dependency_scheduled_time:
                    return True

        return False
        
    def dispatch(self):
        db_session = DBSession()

        try:
            # Check if Scheduled Installs are allowed to run.
            if not db_session.query(SystemOption).first().can_install:
                return
                
            install_jobs = db_session.query(InstallJob).filter(
                and_(InstallJob.scheduled_time <= datetime.datetime.utcnow(),
                     or_(InstallJob.status == JobStatus.SCHEDULED, InstallJob.status == JobStatus.IN_PROGRESS))).\
                order_by(InstallJob.scheduled_time.asc(), InstallJob.id.asc()).all()

            download_job_key_dict = get_download_job_key_dict()

            if len(install_jobs) > 0:

                for install_job in install_jobs:

                    # Only check dependency and pending download for non-monitor jobs. Skip the checks for monitor jobs.
                    if install_job.job_type != InstallJobType.MONITOR:

                        # If there is pending download, don't submit the install job
                        if self.is_pending_on_download(download_job_key_dict, install_job):
                            continue

                        # This install job has a dependency, check if the expected criteria is met
                        if install_job.dependency is not None:
                            if not self.get_install_job_dependency_completed(db_session, install_job):
                                continue

                    install_job_work_unit = install_work_unit.get_work_unit(db_session, install_job)
                    if install_job_work_unit:
                        self.submit_job(install_job_work_unit)
                    else:
                        logger = get_db_session_logger(db_session)
                        logger.exception("The host for install job id {}, action {} is missing. Fail to schedule job.".format(
                            str(install_job.id), install_job.install_action))

        except Exception:
            # print(traceback.format_exc())
            # Purpose ignore.  Otherwise, it may generate continue exception
            pass
        finally:
            db_session.close()

    def get_download_job_key(self, install_job, filename):
        return "{}{}{}{}".format(install_job.user_id, filename, install_job.server_id, install_job.server_directory)

    def is_pending_on_download(self, download_job_key_dict, install_job):
        if install_job.pending_downloads:
            pending_downloads = install_job.pending_downloads.split(',')
            for filename in pending_downloads:
                download_job_key = self.get_download_job_key(install_job, filename)
                if download_job_key in download_job_key_dict:
                    return True
        return False
                


if __name__ == '__main__': 
    pass
