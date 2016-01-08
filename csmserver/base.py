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
from models import JumpHost
from models import SystemOption

from utils import concatenate_dirs
from utils import is_empty
from utils import make_url

from constants import get_temp_directory
from constants import get_autlogs_directory


class Context(object):
    def __init__(self, db_session):
        self.db_session = db_session
        self._success = False
        
    @property
    def success(self):
        return self._success
    
    @success.setter
    def success(self, value):
        self._success = value 
            

class ImageContext(Context):
    def __init__(self, db_session, host):
        Context.__init__(self, db_session)
        self.host = host
            
        self.committed_cli = None
        self.active_cli = None
        self.inactive_cli = None   

    @property
    def data(self):
        return self.host.context[0].data

    @property
    def data_modified_time(self):
        return self.host.context[0].modified_time

    @property
    def host_urls(self):
        urls = []

        if len(self.host.connection_param) > 0:
            connection = self.host.connection_param[0]
            jump_host_url = ''

            # Checks if there is a jump server
            if connection.jump_host_id is not None:
                try:
                    jump_host = self.db_session.query(JumpHost).filter(JumpHost.id == connection.jump_host_id).first()
                    if jump_host is not None:
                        jump_host_url = make_url(
                            connection_type=jump_host.connection_type,
                            username=jump_host.username,
                            password=jump_host.password,
                            host_or_ip=jump_host.host_or_ip,
                            port_number=jump_host.port_number)
                except:
                    pass

            default_username=None
            default_password=None
            system_option = SystemOption.get(self.db_session)

            if system_option.enable_default_host_authentication:
                default_username = system_option.default_host_username
                default_password = system_option.default_host_password

            for host_or_ip in connection.host_or_ip.split(','):
                for port_number in connection.port_number.split(','):
                    host_urls = []
                    if not is_empty(jump_host_url):
                        host_urls.append(jump_host_url)

                    host_urls.append(make_url(
                        connection_type=connection.connection_type,
                        username=connection.username,
                        password=connection.password,
                        host_or_ip=host_or_ip,
                        port_number=port_number,
                        default_username=default_username,
                        default_password=default_password))

                    urls.append(host_urls)

        return urls


class ConnectionContext(Context):
    def __init__(self, db_session, urls):
        Context.__init__(self, db_session)
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
    def __init__(self, db_session, host, inventory_job):
        ImageContext.__init__(self, db_session, host)
        self.inventory_job = inventory_job
        
    @property
    def requested_action(self):
        return 'Get-Package'
    
    @property
    def log_directory(self):
        return get_autlogs_directory() + self.inventory_job.session_log  
    
    def post_status(self, message):
        if self.db_session is not None and self.inventory_job is not None:
            try:
                self.inventory_job.set_status(message)
                self.db_session.commit()
            except:
                self.db_session.rollback()
            
               
class InstallContext(ImageContext):
    def __init__(self, db_session, host, install_job):
        ImageContext.__init__(self, db_session, host)
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

    @property 
    def server_repository_url(self):
        """
        Return the server repository URL (TFTP/FTP) where the packages can be found.
        tftp://223.255.254.254/auto/tftp-gud/sit;VRF
        ftp://username:password@10.55.7.21;VRF/remote/directory
        """
        server_id = self.install_job.server_id
        server = self.db_session.query(Server).filter(Server.id == server_id).first()

        if server is not None:
            server_type = server.server_type

            if server_type == ServerType.TFTP_SERVER:
                url = 'tftp://{}'.format(server.server_url.replace('tftp://',''))

                if not is_empty(server.vrf):
                    url = url + ";{}".format(server.vrf)

                server_sub_directory = self.install_job.server_directory
                
                if not is_empty(server_sub_directory):
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
    
    def post_status(self, message):
        if self.db_session is not None and self.install_job is not None:
            try:
                self.install_job.set_status(message)
                self.db_session.commit()
            except:
                self.db_session.rollback()



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
