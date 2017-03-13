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
from models import Host
from models import InventoryJob
from models import InventoryJobHistory

from constants import JobStatus

from handlers.loader import get_inventory_handler_class
from context import InventoryContext
from utils import create_log_directory

from multi_process import WorkUnit

import traceback
import sys


class InventoryWorkUnit(WorkUnit):
    def __init__(self, host_id, job_id):
        WorkUnit.__init__(self)

        self.host_id = host_id
        self.job_id = job_id

    def get_unique_key(self):
        return self.host_id

    def start(self, db_session, logger, process_name):
        host = None
        inventory_job = None

        try:
            inventory_job = db_session.query(InventoryJob).filter(InventoryJob.id == self.job_id).first()
            if inventory_job is None:
                logger.error('Unable to retrieve inventory job: %s' % self.job_id)
                return

            host_id = inventory_job.host_id
            host = db_session.query(Host).filter(Host.id == host_id).first()
            if host is None:
                logger.error('Unable to retrieve host: %s' % host_id)

            ctx = InventoryContext(db_session, host, inventory_job)

            handler_class = get_inventory_handler_class(ctx)
            if handler_class is None:
                logger.error('Unable to get handler for %s, inventory job %s', host.software_platform, self.job_id)

            inventory_job.set_status(JobStatus.IN_PROGRESS)
            inventory_job.session_log = create_log_directory(host.connection_param[0].host_or_ip, inventory_job.id)
            db_session.commit()

            handler = handler_class()
            handler.execute(ctx)

            if ctx.success:
                self.archive_inventory_job(db_session, inventory_job, JobStatus.COMPLETED)
            else:
                # removes the host object as host.packages may have been modified.
                db_session.expunge(host)
                self.archive_inventory_job(db_session, inventory_job, JobStatus.FAILED)

            db_session.commit()

        except Exception:
            try:
                self.log_exception(logger, host)

                self.archive_inventory_job(db_session, inventory_job, JobStatus.FAILED, trace=sys.exc_info)

                db_session.commit()
            except Exception:
                self.log_exception(logger, host)
        finally:
            db_session.close()

    def log_exception(self, logger, host):
        logger.exception('InventoryManager hit exception - hostname = %s, inventory job =  %s',
                         host.hostname if host is not None else 'Unknown', self.job_id)

    def archive_inventory_job(self, db_session, inventory_job, job_status, trace=None):
        inventory_job.set_status(job_status)

        hist = InventoryJobHistory()
        hist.host_id = inventory_job.host_id
        hist.set_status(job_status)
        hist.session_log = inventory_job.session_log

        if trace is not None:
            hist.trace = traceback.format_exc()

        db_session.add(hist)
