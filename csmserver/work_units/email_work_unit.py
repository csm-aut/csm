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
from multi_process import WorkUnit

from models import SMTPServer
from models import EmailJob

from mailer import sendmail


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

            db_session.delete(email_job)
            db_session.commit()

        finally:
            db_session.close()

    def get_unique_key(self):
        return 'email_job_{}'.format(self.job_id)

