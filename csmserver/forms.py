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
from wtforms import Form
from wtforms import TextAreaField
from wtforms import StringField
from wtforms import SelectField
from wtforms import PasswordField
from wtforms import HiddenField
from wtforms import SelectMultipleField
from wtforms.validators import Length
from wtforms.validators import required
from constants import ConnectionType
from constants import ServerType
from constants import ExportInformationFormat


class HostForm(Form):
    hostname = StringField('Hostname', [required(), Length(max=30)])
    region = SelectField('Region', coerce=int, choices=[(-1, '')])
    location = StringField('Location', [Length(max=100)])
    roles = StringField('Roles')
    software_profile = SelectField('Software Profile', coerce=int, choices=[(-1, '')])
    host_or_ip = StringField('Terminal Server or Mgmt. IP', [required(), Length(max=30)])
    username = StringField('Username')
    password = PasswordField('Password')
    enable_password = PasswordField('Enable Password (IOS-XE only)')
    connection_type = SelectField('Connection Type', coerce=str,
                                  choices=[(ConnectionType.TELNET, ConnectionType.TELNET),
                                           (ConnectionType.SSH, ConnectionType.SSH)])
    port_number = StringField('Port Number')
    jump_host = SelectField('Jump Server', coerce=int, choices=[(-1, 'None')])


class JumpHostForm(Form):
    hostname = StringField('Jump Server', [required(), Length(max=255)])
    host_or_ip = StringField('Name or IP', [required(), Length(max=255)])
    username = StringField('Username')
    password = PasswordField('Password')
    connection_type = SelectField('Connection Type', coerce=str,
                                  choices=[(ConnectionType.TELNET, ConnectionType.TELNET),
                                           (ConnectionType.SSH, ConnectionType.SSH)])
    port_number = StringField('Port Number')


class ServerDialogForm(Form):
    server_dialog_target_software = StringField('Target Software Release')
    server_dialog_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])
    server_dialog_server_directory = SelectField('Server Directory', coerce=str, choices=[('', '')])


class HostScheduleInstallForm(ServerDialogForm):

    install_action = SelectMultipleField('Install Action', coerce=str, choices=[('', '')])

    scheduled_time = StringField('Scheduled Time', [required()])
    scheduled_time_UTC = HiddenField('Scheduled Time')
    software_packages = TextAreaField('Software Packages')
    custom_command_profile = SelectMultipleField('Custom Command Profile', coerce=int, choices=[('', '')])
    # Use str coercion as Batch Schedule Install displays the action Install Action.
    dependency = SelectField('Dependency', coerce=str, choices=[(-1, 'None')])
       
    install_history_dialog_host = SelectField('Host', coerce=str, choices=[('', '')])
    
    host_software_dialog_target_software = StringField('Target Software Release')
    host_software_dialog_host = SelectField('Host', coerce=str, choices=[('', '')])
    host_software_dialog_last_successful_inventory_elapsed_time = StringField('Last Successful Retrieval')

    cisco_dialog_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])
    cisco_dialog_server_directory = SelectField('Server Directory', coerce=str, choices=[('', '')])
    server_modal_dialog_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])

    # For SCP server repository support
    destination_path_on_device = StringField('Destination Path on Device (e.g. harddisk:/file)')

    hidden_selected_hosts = HiddenField('')
    hidden_server = HiddenField('')   
    hidden_server_name = HiddenField('')   
    hidden_server_directory = HiddenField('')
    
    hidden_pending_downloads = HiddenField('Pending Downloads')
    hidden_edit = HiddenField('Edit')


class ScheduleInstallForm(HostScheduleInstallForm):
    platform = SelectField('Platform', coerce=str, choices=[('', '')])
    software = SelectField('Software Version', coerce=str, choices=[('ALL', 'ALL')])
    region = SelectField('Region', coerce=int, choices=[(-1, 'ALL')])
    role = SelectField('Role', coerce=str, choices=[('ALL', 'ALL')])


class ServerForm(Form):
    hostname = StringField('Server Repository Name', [required()])
    server_type = SelectField('Server Type', coerce=str,
                              choices=[(ServerType.TFTP_SERVER, ServerType.TFTP_SERVER),
                                       (ServerType.FTP_SERVER, ServerType.FTP_SERVER),
                                       (ServerType.SFTP_SERVER, ServerType.SFTP_SERVER),
                                       (ServerType.SCP_SERVER, ServerType.SCP_SERVER),
                                       (ServerType.LOCAL_SERVER, ServerType.LOCAL_SERVER)])
    server_url = StringField('Server URL (for device)', [required()])
    username = StringField('Username')
    password = PasswordField('Password')
    server_directory = StringField('Home Directory')
    vrf = StringField('VRF')
    destination_on_host = StringField('Destination on Host (e.g. /harddisk:)')


class RegionForm(Form):
    region_name = StringField('Region Name', [required()])


class BrowseServerDialogForm(Form):
    dialog_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])


class SelectServerForm(Form):
    select_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])
    select_server_directory = SelectField('Server Directory', coerce=str, choices=[('', '')])


class SoftwareProfileForm(Form):
    software_profile_name = StringField('Software Profile Name', [required(), Length(max=30)])


class ExportInformationForm(Form):
    export_format = SelectField('Export Format', coerce=str,
                                choices=[(ExportInformationFormat.HTML,
                                          ExportInformationFormat.HTML),
                                         (ExportInformationFormat.MICROSOFT_EXCEL,
                                          ExportInformationFormat.MICROSOFT_EXCEL)])


if __name__ == '__main__':
    pass
