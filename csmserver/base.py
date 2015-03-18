
from constants import ServerType
from models import Server
from utils import concatenate_dirs
from constants import get_temp_directory, get_autlogs_directory

class Context(object):
    def __init__(self):
        self._success = False
        
    @property
    def success(self):
        return self._success
    
    @success.setter
    def success(self, value):
        self._success = value 
            

class ImageContext(Context):
    def __init__(self, host, db_session):
        Context.__init__(self)
        self.host = host
        self.db_session = db_session   
            
        self.committed_cli = None
        self.active_cli = None
        self.inactive_cli = None   
        
    @property
    def host_urls(self): 
        return self.host.urls     

class ConnectionContext(Context):
    def __init__(self, urls):
        Context.__init__(self)
        self.urls = urls

    @property
    def requested_action(self):
        return 'Get-Package'

    @property
    def log_directory(self):
        return get_temp_directory()

    def post_status(self, message):
        pass
    
    @property
    def host_urls(self): 
        return self.urls 

class InventoryContext(ImageContext):
    def __init__(self, host, db_session, inventory_job):
        ImageContext.__init__(self, host, db_session)
        self.inventory_job = inventory_job
        
    @property
    def requested_action(self):
        return 'Get-Package'
    
    @property
    def log_directory(self):
        return get_autlogs_directory() + self.inventory_job.session_log  
    
    def post_status(self, message):
        if self.db_session is not None and \
            self.inventory_job is not None:
            self.inventory_job.set_status(message)
            self.db_session.commit() 
            
               
class InstallContext(ImageContext):
    def __init__(self, host, db_session, install_job):
        ImageContext.__init__(self, host, db_session)
        self.install_job = install_job
        self._operation_id = -1
    
    @property
    def software_packages(self):
        return self.install_job.packages.split(',')
    
    @property
    def requested_action(self):
        return self.install_job.install_action
    
    @property
    def log_directory(self):
        return get_autlogs_directory() + self.install_job.session_log 
    
    @property
    def operation_id(self):
        return self._operation_id
    
    @operation_id.setter
    def operation_id(self, value):
        try:
            self._operation_id = int(value)
        except:  
            self._operation_id = -1
    
    """
    Return the server repository URL (TFTP/FTP) where the packages can be found.
    """
    @property 
    def server_repository_url(self):
        server_id = self.install_job.server_id
        server = self.db_session.query(Server).filter(Server.id == server_id).first()

        if server is not None:
            server_type = server.server_type

            if server_type == ServerType.TFTP_SERVER:
                url = server.server_url
                server_sub_directory = self.install_job.server_directory
                
                if server_sub_directory is not None and len(server_sub_directory) > 0:
                    url += '/' + server_sub_directory                       
                return url
            
            elif server_type == ServerType.FTP_SERVER or server_type == ServerType.SFTP_SERVER:                              
                protocol = 'ftp' if server_type == ServerType.FTP_SERVER else 'sftp'
                url = protocol + "://{}:{}@{}".format(server.username, server.password, server.server_url) 
                
                remote_directory = concatenate_dirs(server.server_directory, self.install_job.server_directory)              
                if len(remote_directory) > 0:
                    url = url + "/{}".format(remote_directory)
                return url
        
        return None
    
    def post_status(self, message):
        if self.db_session is not None and \
            self.install_job is not None:
            self.install_job.set_status(message)
            self.db_session.commit()              
                
class BaseHandler(object):
    def execute(self, ctx):
        raise NotImplementedError("Children must override execute")

class BaseConnection(object):
    def login(self):       
        raise NotImplementedError("Children must override login")
    
    def send_command(self):
        raise NotImplementedError("Children must override send_command")
    
    def logout(self):
        raise NotImplementedError("Children must override logout")
        