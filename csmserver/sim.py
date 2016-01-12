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
from models import InventoryJob

from multi_process import JobManager
from work_units.inventory_work_unit import InventoryWorkUnit


class InventoryManager(JobManager):
    def __init__(self, num_workers, worker_name):
        JobManager.__init__(self, num_workers=num_workers, worker_name=worker_name)
     
    def dispatch(self):
        db_session = DBSession()
        try:
            inventory_jobs = db_session.query(InventoryJob).filter(InventoryJob.pending_submit == True).all()

            if len(inventory_jobs) > 0:
                for inventory_job in inventory_jobs:
                    self.submit_job(InventoryWorkUnit(inventory_job.host_id, inventory_job.id))

        except Exception:
            logger.exception('Unable to dispatch inventory job')  
        finally:
            db_session.close()

if __name__ == '__main__':
    pass
