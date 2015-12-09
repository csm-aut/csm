from work_unit import WorkUnit

from models import SMTPServer
from models import EmailJob

from mailer import sendmail
from constants import JobStatus

class EmailWorkUnit(WorkUnit):
    def __init__(self, job_id):
        WorkUnit.__init__(self)

        self.job_id = job_id

    def start(self, db_session, logger, process_name):
        try:
            smtp_server = db_session.query(SMTPServer).first()
            if smtp_server is None:
                logger.error('mailer: SMTP Server has not been specified')
                return

            email_job = db_session.query(EmailJob).filter(EmailJob.id == self.job_id).first()
            if email_job is None:
                logger.error('Unable to retrieve email job: %s' % self.job_id)
                return

            sendmail(
                logger=logger,
                server=smtp_server.server,
                server_port=smtp_server.server_port,
                sender=smtp_server.sender,
                recipient=email_job.recipients,
                message=email_job.message,
                use_authentication=smtp_server.use_authentication,
                username=smtp_server.username,
                password=smtp_server.password,
                secure_connection=smtp_server.secure_connection)

            email_job.set_status(JobStatus.COMPLETED)
            db_session.commit()

        finally:
            db_session.close()

    def get_unique_key(self):
        return 'email_job_{}'.format(self.job_id)

