# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
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
from wtforms import Form, validators
from wtforms import TextAreaField, StringField, TextField, IntegerField, SelectField, PasswordField, HiddenField, SelectMultipleField
from wtforms.validators import Length, required
from constants import Platform, ConnectionType, ServerType, UserPrivilege, SMTPSecureConnection

class LoginForm(Form):
    """
    Render HTML input for user login form.
    Authentication (i.e. password verification) happens in the view function.
    """
    username = StringField('Username', [required()])
    password = PasswordField('Password', [required()])
    
class UserForm(Form):
    """
    Render HTML input for user registration form.
    Authentication (i.e. password verification) happens in the view function.
    """
    username = StringField('Username', [required()])
    password = PasswordField('Password', [required()])
    privilege = SelectField('Privilege', [required()], coerce=str,
        choices = [('', ''),
                   (UserPrivilege.ADMIN, UserPrivilege.ADMIN),  
                   (UserPrivilege.NETWORK_ADMIN, UserPrivilege.NETWORK_ADMIN), 
                   (UserPrivilege.OPERATOR, UserPrivilege.OPERATOR), 
                   (UserPrivilege.VIEWER, UserPrivilege.VIEWER)])
    active = HiddenField("Active")
    fullname = StringField('Full Name', [required()])
    email = StringField('Email Address', [required()])
    
class HostForm(Form):
    hostname = StringField('Hostname', [required(), Length(max=30)])
    platform = SelectField('Platform', coerce=str,
        choices = [(Platform.ASR9K, Platform.ASR9K),  
                   (Platform.CRS,Platform.CRS)])
    region = SelectField('Region', coerce=int, choices = [(-1, '')])
    roles = StringField('Roles')
    host_or_ip = StringField('Terminal Server or Mgmt. IP', [required(), Length(max=30)])
    username = StringField('Username')
    password = PasswordField('Password')
    connection_type = SelectField('Connection Type', coerce=str,
        choices = [(ConnectionType.TELNET, ConnectionType.TELNET), 
                   (ConnectionType.SSH, ConnectionType.SSH)])
    port_number = StringField('Port Number')
    jump_host = SelectField('Jump Server', coerce=int, choices = [(-1, 'None')])

class JumpHostForm(Form):
    hostname = StringField('Jump Server', [required(), Length(max=255)])
    host_or_ip = StringField('Name or IP', [required(), Length(max=255)])
    username = StringField('Username')
    password = PasswordField('Password')
    connection_type = SelectField('Connection Type', coerce=str,
        choices = [(ConnectionType.TELNET, ConnectionType.TELNET), 
                   (ConnectionType.SSH, ConnectionType.SSH)])

    port_number = StringField('Port Number')


class ServerDialogForm(Form):
    server_dialog_target_software = StringField('Target Software Release')
    server_dialog_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])
    server_dialog_server_directory = SelectField('Server Directory', coerce=str, choices=[('', '')])


class HostScheduleInstallForm(ServerDialogForm):

    install_action = SelectMultipleField('Install Action', coerce=str, choices = [('', '')])
       
    scheduled_time = StringField('Scheduled Time', [required()])
    scheduled_time_UTC = HiddenField('Scheduled Time')
    software_packages = TextAreaField('Software Packages')
    dependency = SelectField('Dependency', coerce=str, choices = [(-1, 'None')])        
       
    install_history_dialog_host = SelectField('Host', coerce=str, choices = [('', '')])
    
    host_software_dialog_target_software = StringField('Target Software Release')
    host_software_dialog_host = SelectField('Host', coerce=str, choices = [('', '')])
    host_software_dialog_last_successful_inventory_elapsed_time = StringField('Last Successful Retrieval')

    cisco_dialog_server = SelectField('Server Repository', coerce=int, choices = [(-1, '')]) 
    cisco_dialog_server_directory = SelectField('Server Directory', coerce=str, choices = [('', '')])
    
    hidden_server = HiddenField('')   
    hidden_server_name = HiddenField('')   
    hidden_server_directory = HiddenField('')
    
    hidden_pending_downloads = HiddenField('Pending Downloads')
    hidden_edit = HiddenField('Edit')
    
class ScheduleInstallForm(HostScheduleInstallForm):
    region = SelectField('Region', coerce=int, choices = [(-1, '')]) 
    role = SelectField('Role', coerce=str, choices = [('ALL', 'ALL')])
    software = SelectField('Software Version', coerce=str, choices = [('ALL', 'ALL')])
    
class ServerForm(Form):
    hostname = StringField('Server Repository Name', [required()])
    server_type = SelectField('Server Type', coerce=str,
        choices = [(ServerType.TFTP_SERVER, ServerType.TFTP_SERVER), 
                   (ServerType.FTP_SERVER, ServerType.FTP_SERVER),
                   (ServerType.SFTP_SERVER, ServerType.SFTP_SERVER),
                   (ServerType.LOCAL_SERVER, ServerType.LOCAL_SERVER)])
    server_url = StringField('Server URL (for device)', [required()])
    username = StringField('Username')
    password = PasswordField('Password')
    server_directory = StringField('File Directory')
    vrf = StringField('VRF')
    
class RegionForm(Form):
    region_name = StringField('Region Name', [required()])
    
class AdminConsoleForm(Form):
    num_inventory_threads = IntegerField('Number of Software Inventory Processes', [validators.NumberRange(min=2, max=50)])
    num_install_threads = IntegerField('Number of Install Processes', [validators.NumberRange(min=2, max=100)])
    num_download_threads = IntegerField('Number of SMU Download Processes', [validators.NumberRange(min=2, max=50)])
    can_schedule = HiddenField("Allow Users to Schedule Install")
    can_install = HiddenField("Allow Scheduled Installs to Run")
    enable_email_notify = HiddenField("Enable Email Notification")
    enable_inventory = HiddenField("Enable Software Inventory")
    inventory_hour = SelectField('Hour to Perform Software Inventory', coerce=int, 
        choices = [(0, '12:00 AM'), (1, '01:00 AM'), (2, '02:00 AM'), (3, '03:00 AM'), (4, '04:00 AM'), (5, '05:00 AM'),
                   (6, '06:00 AM'), (7, '07:00 AM'), (8, '08:00 AM'), (9, '09:00 AM'), (10, '10:00 AM'), (11, '11:00 AM'),
                   (12, '12:00 PM'), (13, '01:00 PM'), (14, '02:00 PM'), (15, '03:00 PM'), (16, '04:00 PM'), (17, '05:00 PM'),
                   (18, '06:00 PM'), (19, '07:00 PM'), (20, '08:00 PM'), (21, '09:00 PM'), (22, '10:00 PM'), (23, '11:00 PM'),
                  ]) 
    inventory_history_per_host = IntegerField('Software Inventory History Per Host', [validators.NumberRange(min=10, max=100)])
    install_history_per_host = IntegerField('Install History Per Host', [validators.NumberRange(min=10, max=1000)])
    download_history_per_user = IntegerField('SMU/SP Download History Per User', [validators.NumberRange(min=10, max=100)])
    total_system_logs = IntegerField('Total System Logs', [validators.NumberRange(min=100, max=100000)])
    enable_default_host_authentication = HiddenField("Enable Default Host Authentication")
    default_host_username = StringField('Default Host Username')
    default_host_password = PasswordField('Default Host Password')
    enable_ldap_auth = HiddenField("Enable LDAP")
    ldap_server_url = StringField('LDAP Server URL')
    enable_cco_lookup = HiddenField("Enable CCO Connection")
    cco_lookup_time = HiddenField("Last Retrieval")


class SMTPForm(Form):
    server = StringField('Outgoing SMTP Server')
    server_port = StringField('SMTP Server Port')
    sender = StringField('Sender Email Address')
    use_authentication = HiddenField("Server uses Authentication")
    username = StringField('Username')
    password = PasswordField('Password')
    secure_connection = SelectField('Secure Connection', coerce=str,
        choices = [(SMTPSecureConnection.SSL, SMTPSecureConnection.SSL), 
                   (SMTPSecureConnection.TLS, SMTPSecureConnection.TLS)])

class PreferencesForm(Form):
    cco_username = StringField('Username')
    cco_password = PasswordField('Password')


class BrowseServerDialogForm(Form):
    dialog_server = SelectField('Server Repository', coerce=int, choices = [(-1, '')])


class SelectServerForm(Form):
    select_server= SelectField('Server Repository', coerce=int, choices=[(-1, '')])
    select_server_directory = SelectField('Server Directory', coerce=str, choices=[('', '')])


class SoftwareProfileForm(Form):
    profile_name = StringField('Profile Name', [required(), Length(max=30)])
    description = StringField('Description', [required(), Length(max=100)])

if __name__ == '__main__':
    pass
    
