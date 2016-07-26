import subprocess

from constants import get_migration_directory, JobStatus
from models import ConvertConfigJob
from multi_process import WorkUnit

NOX_64_BINARY = "nox-linux-64.bin"
NOX_64_MAC = "nox-mac64.bin"


class ConvertConfigWorkUnit(WorkUnit):
    def __init__(self, job_id):
        WorkUnit.__init__(self)

        self.job_id = job_id

    def start(self, db_session, logger, process_name):
        self.db_session = db_session
        try:
            self.convert_config_job = self.db_session.query(ConvertConfigJob).filter(ConvertConfigJob.id ==
                                                                                     self.job_id).first()
            if self.convert_config_job is None:
                logger.error('Unable to retrieve convert config job: %s' % self.job_id)
                return

            self.convert_config_job.set_status("Converting the Configurations")
            self.db_session.commit()

            file_path = self.convert_config_job.file_path

            nox_to_use = get_migration_directory() + NOX_64_BINARY
            # nox_to_use = get_migration_directory() + NOX_64_MAC
            print "start executing nox conversion..."
            try:
                commands = [subprocess.Popen(["chmod", "+x", nox_to_use]),
                            subprocess.Popen([nox_to_use, "-f", file_path],
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            ]

                nox_output, nox_error = commands[1].communicate()
                print "the nox finished its job."
            except OSError:
                self.convert_config_job.set_status(JobStatus.FAILED)
                self.db_session.commit()
                logger.exception("OSError occurred while running the configuration migration tool " +
                                 "{} on config file {}.".format(nox_to_use, file_path))

            if nox_error:
                self.convert_config_job.set_status(JobStatus.FAILED)
                self.db_session.commit()
                logger.exception("Error running the configuration migration tool on {}".format(nox_error))
            else:
                self.convert_config_job.set_status(JobStatus.COMPLETED)
                self.db_session.commit()

        finally:
            self.db_session.close()

    def get_unique_key(self):
        return 'convert_config_job_{}'.format(self.job_id)
