# =============================================================================
# Copyright (c)  2015, Cisco Systems, Inc
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

from constants import ServerType
from models import Server
from utils import concatenate_dirs, is_empty
from constants import get_temp_directory, get_autlogs_directory, get_migration_directory

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

    @property
    def migration_directory(self):
        return get_migration_directory()

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

    @property
    def migration_directory(self):
        return get_migration_directory()
    
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
    def migration_directory(self):
        return get_migration_directory()
    
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
    tftp://223.255.254.254/auto/tftp-gud/sit;VRF
    ftp://username:password@10.55.7.21;VRF/remote/directory
    """
    @property 
    def server_repository_url(self):
        server_id = self.install_job.server_id
        server = self.db_session.query(Server).filter(Server.id == server_id).first()

        if server is not None:
            server_type = server.server_type

            if server_type == ServerType.TFTP_SERVER:
                url = 'tftp://{}'.format(server.server_url.replace('tftp://',''))

                if not is_empty(server.vrf):
                    url = url + ";{}".format(server.vrf)

                server_sub_directory = self.install_job.server_directory
                
                if server_sub_directory is not None and not is_empty(server_sub_directory):
                    url += '/' + server_sub_directory  
                
                return url
            
            elif server_type == ServerType.FTP_SERVER or server_type == ServerType.SFTP_SERVER:                              
                protocol = 'ftp' if server_type == ServerType.FTP_SERVER else 'sftp'
                url = protocol + "://{}:{}@{}".format(server.username, server.password, server.server_url) 
                
                if not is_empty(server.vrf):
                    url = url + ";{}".format(server.vrf)

                remote_directory = concatenate_dirs(server.server_directory, self.install_job.server_directory)              
                if not is_empty(remote_directory):
                    url = url + "/{}".format(remote_directory)

                return url
            elif server_type == ServerType.LOCAL_SERVER:
                return server.server_url
        
        return None

    @property
    def post_migrate_config_handling_option(self):
        return self.install_job.best_effort_config_applying
    
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
        
