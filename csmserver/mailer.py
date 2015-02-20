import smtplib

from database import DBSession
from constants import JobStatus
from constants import SMTPSecureConnection

from models import SMTPServer
from models import User
from models import logger
from models import Host
from models import SystemOption

from filters import get_datetime_string

# Import the email modules we'll need
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_install_status_email(install_job):
    db_session = DBSession
    username = install_job.created_by

    system_option = SystemOption.get(db_session)
    if not system_option.enable_email_notify:
        return
    
    smtp_server = get_smtp_server(db_session)
    if smtp_server is None:
        logger.error('mailer: SMTP Server has not been specified')
        return
    
    user = get_user(db_session, username)
    if user is None:
        logger.error('mailer: Unable to locate user "%s"' % username)
        return
    
    host = get_host(db_session, install_job.host_id)
    if host is None:
        logger.error('mailer: Unable to locate host id "%s"' % str(install_job.host_id))
        return
    
    message = '<html><head><body>'
    if install_job.status == JobStatus.COMPLETED:
        message += 'The scheduled installation for host "' + host.hostname + '" has COMPLETED<br><br>'
    elif install_job.status == JobStatus.FAILED:
        message += 'The scheduled installation for host "' + host.hostname + '" has FAILED<br><br>'
    
    message += 'Scheduled Time: ' + get_datetime_string(install_job.scheduled_time) + ' (UTC)<br>'    
    message += 'Start Time: ' + get_datetime_string(install_job.start_time) + ' (UTC)<br>'
    message += 'Install Action: ' + install_job.install_action + '<br><br>'
    
    if install_job.packages is not None and len(install_job.packages) > 0:
        message += 'Following are the Selected Packages: <br>' + install_job.packages.replace('\n','<br>')
        
    message += '</body></head></html>'
    
    sendmail(
        server=smtp_server.server, 
        server_port=smtp_server.server_port,
        sender=smtp_server.sender,
        recipient=user.email,
        message=message,
        use_authentication=smtp_server.use_authentication,
        username=smtp_server.username,
        password=smtp_server.password,
        secure_connection=smtp_server.secure_connection)
        
def sendmail(server, server_port, sender, recipient, 
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

    except:
        logger.exception('sendmail hit exception')
     
        
def get_smtp_server(db_session):
    return db_session.query(SMTPServer).first()

def get_user(db_session, username):
    return db_session.query(User).filter(User.username == username).first()

def get_host(db_session, id):
    return db_session.query(Host).filter(Host.id == id).first()

def test_sendmail(sender, recipient):
    """
    msg['Subject'] = 'The contents of %s' % textfile
    msg['From'] = 'alextang.cisco.com'
    msg['To'] = 'alextang.cisco.com'
    """
    
    s = smtplib.SMTP('localhost')
    s.sendmail(sender, recipient, "this is a test")
    s.quit()

    
if __name__ == '__main__':
    test_sendmail('alextang@cisco.com', 'alextang.lds@gmail.com')