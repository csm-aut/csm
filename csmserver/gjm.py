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
import time
import threading

from database import DBSession
from models import logger
from models import EmailJob

from process_pool import Pool
from work_units import EmailWorkUnit


class GenericJobManager(threading.Thread):
    def __init__(self, name, num_threads=4):
        threading.Thread.__init__(self, name = name)
        self.pool = Pool(num_workers=num_threads, name="Generic-Job")

    def run(self):
        while 1:
            time.sleep(20)
            self.dispatch()

    def dispatch(self):
        db_session = DBSession()
        try:
            # Submit email notification jobs if any
            email_jobs = db_session.query(EmailJob).filter(EmailJob.status == None).all()
            if len(email_jobs) > 0:
                for email_job in email_jobs:
                    self.pool.submit(EmailWorkUnit(email_job.id))

        except:
            logger.exception('Unable to dispatch job')
        finally:
            db_session.close()

if __name__ == "__main__":

    db_session = DBSession()
    job = EmailJob(recipients='alextang@cisco.com', message="testing")
    db_session.add(job)
    db_session.commit()

    """
    generic_job_manager = GenericJobManager('Generic Job Manager')
    generic_job_manager.start()
    """