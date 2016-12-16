#=============================================================================
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
from constants import ServerType

from models import Server

from models import JumpHost
from models import SystemOption
from models import CustomCommandProfile

from utils import concatenate_dirs
from utils import is_empty
from utils import make_url

from constants import get_temp_directory

from constants import get_log_directory
from constants import get_migration_directory

from common import get_user_by_id
from constants import DefaultHostAuthenticationChoice


class Context(object):
    def __init__(self):
        self._success = False
        
    @property
    def success(self):
        return self._success
    
    @success.setter
    def success(self, value):
        self._success = value 


class ConnectionContext(Context):
    def __init__(self, db_session, host):
        Context.__init__(self)
        self.host = host
        self.db_session = db_session

    @property
    def hostname(self):
        return self.host.hostname

    def load_data(self, key):
        return self.host.context[0].data.get(key)

    def save_data(self, key, value):
        self.host.context[0].data[key] = value

    def get_data_modified_time(self):
        return self.host.context[0].modified_time

    @property
    def host_urls(self):
        return self.make_urls()

    def make_urls(self, preferred_host_username=None, preferred_host_password=None):
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
                            host_username=jump_host.username,
                            host_password=jump_host.password,
                            host_or_ip=jump_host.host_or_ip,
                            port_number=jump_host.port_number)
                except:
                    pass

            host_username = connection.username
            host_password = connection.password

            if not is_empty(preferred_host_username) and not is_empty(preferred_host_password):
                host_username = preferred_host_username
                host_password = preferred_host_password
            else:
                system_option = SystemOption.get(self.db_session)
                if system_option.enable_default_host_authentication:
                    if not is_empty(system_option.default_host_username) and not is_empty(system_option.default_host_password):
                        if system_option.default_host_authentication_choice == DefaultHostAuthenticationChoice.ALL_HOSTS or \
                            (system_option.default_host_authentication_choice ==
                                DefaultHostAuthenticationChoice.HOSTS_WITH_NO_SPECIFIED_USERNAME_AND_PASSWORD and
                                is_empty(host_username) and
                                is_empty(host_password)):
                            host_username = system_option.default_host_username
                            host_password = system_option.default_host_password

            for host_or_ip in connection.host_or_ip.split(','):
                for port_number in connection.port_number.split(','):
                    host_urls = []
                    if not is_empty(jump_host_url):
                        host_urls.append(jump_host_url)

                    host_urls.append(make_url(
                        connection_type=connection.connection_type,
                        host_username=host_username,
                        host_password=host_password,
                        host_or_ip=host_or_ip,
                        port_number=port_number,
                        enable_password=connection.enable_password))

                    urls.append(host_urls)

        return urls


class InventoryContext(ConnectionContext):
    def __init__(self, db_session, host, inventory_job):
        ConnectionContext.__init__(self, db_session, host)
        self.inventory_job = inventory_job

    @property
    def log_directory(self):
        return get_log_directory() + self.inventory_job.session_log

    @property
    def requested_action(self):
        return 'Get-Software-Packages'

    def post_status(self, message):
        if self.db_session is not None and self.inventory_job is not None:
            try:
                self.inventory_job.set_status(message)
                self.db_session.commit()
            except Exception:
                self.db_session.rollback()
            
               
class InstallContext(ConnectionContext):
    def __init__(self, db_session, host, install_job):
        ConnectionContext.__init__(self, db_session, host)
        self.install_job = install_job
        self._operation_id = -1

        self.custom_commands = []
        custom_command_profile_ids = self.install_job.custom_command_profile_id
        if custom_command_profile_ids:
            for id in custom_command_profile_ids.split(','):
                profile = self.db_session.query(CustomCommandProfile).filter(CustomCommandProfile.id == id).first()
                if profile:
                    for command in profile.command_list.split(','):
                        if command not in self.custom_commands:
                            self.custom_commands.append(command)

    @property
    def software_packages(self):
        return self.install_job.packages.split(',')
    
    @property
    def requested_action(self):
        return self.install_job.install_action
    
    @property
    def log_directory(self):
        return get_log_directory() + self.install_job.session_log

    @property
    def migration_directory(self):
        return get_migration_directory()

    @property
    def custom_commands(self):
        return self._custom_commands

    @custom_commands.setter
    def custom_commands(self, value):
        self._custom_commands = value

    @property
    def operation_id(self):
        return self._operation_id
    
    @operation_id.setter
    def operation_id(self, value):
        try:
            self._operation_id = int(value)
        except Exception:
            self._operation_id = -1

    @property
    def host_urls(self):
        system_option = SystemOption.get(self.db_session)
        if system_option.enable_user_credential_for_host:
            user = get_user_by_id(self.db_session, self.install_job.user_id)
            if user is not None:
                return self.make_urls(user.username, user.host_password)

        return self.make_urls()

    @property 
    def get_server(self):
        """
        Return the user selected server object where the packages can be found.
        """
        server_id = self.install_job.server_id
        server = self.db_session.query(Server).filter(Server.id == server_id).first()
        return server

    @property
    def get_host(self):
        """
        Return the host object.
        """
        return self.host

    @property 
    def server_repository_url(self):
        """
        Return the server repository URL (TFTP/FTP) where the packages can be found.
        tftp://223.255.254.254;VRF/auto/tftp-gud/sit
        ftp://username:password@10.55.7.21;VRF/remote/directory
        """
        server_id = self.install_job.server_id
        server = self.db_session.query(Server).filter(Server.id == server_id).first()

        if server is not None:
            server_type = server.server_type

            if server_type == ServerType.TFTP_SERVER:
                tftp_string = 'tftp://'
                url = '{}{}'.format(tftp_string, server.server_url.replace(tftp_string, ''))

                if not is_empty(server.vrf):
                    try:
                        pos = url.index('/', len(tftp_string))
                    except ValueError:
                        pos = len(url)
                    url = url[:pos] + ';' + server.vrf + url[pos:]

                server_sub_directory = self.install_job.server_directory
                
                if not is_empty(server_sub_directory):
                    url += '/' + server_sub_directory  

                return url
            
            elif server_type == ServerType.FTP_SERVER or server_type == ServerType.SFTP_SERVER:                              
                protocol = 'ftp' if server_type == ServerType.FTP_SERVER else 'sftp'
                url = protocol + "://{}:{}@{}".format(server.username, server.password, server.server_url) 
                
                if server_type == ServerType.FTP_SERVER and not is_empty(server.vrf):
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
            except Exception:
                self.db_session.rollback()


class TestConnectionContext(Context):
    def __init__(self, hostname, urls):
        Context.__init__(self)
        self.hostname = hostname
        self.urls = urls

    @property
    def log_directory(self):
        return get_temp_directory()

    def post_status(self, message):
        pass

    @property
    def host_urls(self):
        return self.urls
