from models import Host
from models import InventoryJob
from models import InventoryJobHistory

from constants import JobStatus

from handlers.loader import get_inventory_handler_class
from base import InventoryContext
from utils import create_log_directory

from multi_process import WorkUnit

import traceback

class InventoryWorkUnit(WorkUnit):
    def __init__(self, host_id, job_id):
        WorkUnit.__init__(self)

        self.host_id = host_id
        self.job_id = job_id

    def get_unique_key(self):
        return self.host_id

    def start(self, db_session, logger, process_name):
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

            handler_class = get_inventory_handler_class(host.platform)
            if handler_class is None:
                logger.error('Unable to get handler for %s, inventory job %s', host.platform, self.job_id)

            inventory_job.set_status(JobStatus.PROCESSING)
            inventory_job.session_log = create_log_directory(host.connection_param[0].host_or_ip, inventory_job.id)
            db_session.commit()

            ctx = InventoryContext(db_session, host, inventory_job)

            handler = handler_class()
            handler.execute(ctx)

            if ctx.success:
                self.archive_inventory_job(db_session, inventory_job, JobStatus.COMPLETED)
            else:
                # removes the host object as host.packages may have been modified.
                db_session.expunge(host)
                self.archive_inventory_job(db_session, inventory_job, JobStatus.FAILED)

            # Reset the pending retrieval flag
            inventory_job.pending_submit = False
            db_session.commit()

        except Exception:
            try:
                logger.exception('InventoryManager hit exception - inventory job = %s', self.job_id)

                self.archive_inventory_job(db_session, inventory_job, JobStatus.FAILED, trace=sys.exc_info)

                # Reset the pending retrieval flag
                inventory_job.pending_submit = False
                db_session.commit()
            except Exception:
                logger.exception('InventoryManager hit exception - inventory job = %s', self.job_id)
        finally:
            db_session.close()

    def archive_inventory_job(self, db_session, inventory_job, job_status, trace=None):
        inventory_job.set_status(job_status)

        hist = InventoryJobHistory()
        hist.host_id = inventory_job.host_id
        hist.set_status(job_status)
        hist.session_log = inventory_job.session_log

        if trace is not None:
            hist.trace = traceback.format_exc()

        db_session.add(hist)