from multi_process import WorkUnit

from models import CreateTarJob

class CreateTarWorkUnit(WorkUnit):
    def __init__(self, job_id):
        WorkUnit.__init__(self)

        self.job_id = job_id

    def start(self, db_session, logger, process_name):
        try:
            create_tar_job = db_session.query(CreateTarJob).filter(CreateTarJob.id == self.job_id).first()
            if create_tar_job is None:
                logger.error('Unable to retrieve create tar job: %s' % self.job_id)
                return

            server_id = create_tar_job.server_id
            server_directory = create_tar_job.server_directory
            source_tars = create_tar_job.source_tars
            contents = create_tar_job.contents
            sps = create_tar_job.sps
            new_tar_name = create_tar_job.new_tar_name

            // api_create_tar_file() ??

            db_session.delete(create_tar_job)
            db_session.commit()

        finally:
            db_session.close()

    def get_unique_key(self):
        return 'email_job_{}'.format(self.job_id)

