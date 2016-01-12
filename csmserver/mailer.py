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
import smtplib


from constants import JobStatus
from constants import SMTPSecureConnection

from models import SMTPServer
from models import User
from models import Host
from models import SystemOption
from models import EmailJob

# Import the email modules we'll need
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def create_email_job(db_session, logger, message, username):
    system_option = SystemOption.get(db_session)
    if not system_option.enable_email_notify:
        return
    
    user = get_user(db_session, username)
    if user is None:
        logger.error('mailer: Unable to locate user "%s"' % username)
        return

    email_job = EmailJob(recipients=user.email, message=message, created_by=username)
    db_session.add(email_job)
    db_session.commit()

        
def sendmail(logger, server, server_port, sender, recipient,
    message, use_authentication, username, password, secure_connection):

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Notification from CSM Server'
        msg['From'] = sender
        msg['To'] = recipient
        
        part = MIMEText(message, 'html')
        msg.attach(part)
        
        if use_authentication:           
            if secure_connection == SMTPSecureConnection.SSL:
                s = smtplib.SMTP_SSL(server, int(server_port))
            elif secure_connection == SMTPSecureConnection.TLS:
                s = smtplib.SMTP(server, int(server_port))
                s.starttls()
            
            s.login(username, password)
        else:
            if server_port is None or len(server_port) == 0:
                s = smtplib.SMTP(server)
            else:
                s = smtplib.SMTP(server, int(server_port))
       
        s.sendmail(sender, recipient.split(","), msg.as_string()) 
        s.close()

        return True
    except:
        logger.exception('sendmail hit exception')
        return False


def get_user(db_session, username):
    return db_session.query(User).filter(User.username == username).first()
