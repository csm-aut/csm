"""
A WorkUnit instance defines the Work which will be processed by a worker as defined
in the process_pool class.  The Job Manager handles the dispatching of the WorkUnit.
It allows only one unique instance of the WorkUnit as defined by get_unique_key()
to be executed.
"""
class WorkUnit(object):
    """
    Derived class must call the constructor
    """
    def __init__(self):
        self.in_progress_jobs = None
        self.lock = None

    def process(self, db_session, logger, process_name):
        try:
            self.start(db_session, logger, process_name)
        except Exception:
            logger.exception("WorkUnit.process() hit exception")
        finally:
            if self.in_progress_jobs is not None and self.lock is not None:
                with self.lock:
                    if self.get_unique_key() in self.in_progress_jobs: self.in_progress_jobs.remove(self.get_unique_key())

    def start(self, db_session, logger, process_name):
        raise NotImplementedError("Children must override start()")

    """
    Returns an unique value which represents this instance.  An example is an
    unique prefix with the job id from a specific DB table (e.g. email_job_1).
    """
    def get_unique_key(self):
        raise NotImplementedError("Children must override get_unique_key()")