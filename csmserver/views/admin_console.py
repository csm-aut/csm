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
from flask import Blueprint

from flask import render_template
from flask import abort
from flask import request, redirect, url_for
from flask.ext.login import current_user
from flask.ext.login import login_required

from wtforms import Form, validators
from wtforms import RadioField
from wtforms import StringField
from wtforms import IntegerField
from wtforms import SelectField
from wtforms import PasswordField
from wtforms import HiddenField
from wtforms.validators import required

from database import DBSession

from common import get_smtp_server
from common import fill_user_privileges

from constants import UserPrivilege
from constants import SMTPSecureConnection
from constants import DefaultHostAuthenticationChoice

from models import SystemOption
from models import SMTPServer

from utils import is_empty
from utils import is_ldap_supported

from filters import get_datetime_string

admin_console = Blueprint('admin_console', __name__, url_prefix='/admin_console')


@admin_console.route('/', methods=['GET','POST'])
@login_required
def home():
    if current_user.privilege != UserPrivilege.ADMIN:
        abort(401)

    db_session = DBSession()

    smtp_form = SMTPForm(request.form)
    admin_console_form = AdminConsoleForm(request.form)

    smtp_server = get_smtp_server(db_session)
    system_option = SystemOption.get(db_session)

    fill_user_privileges(admin_console_form.ldap_default_user_privilege.choices)

    if request.method == 'POST' and \
        smtp_form.validate() and \
        admin_console_form.validate():

        if smtp_server is None:
            smtp_server = SMTPServer()
            db_session.add(smtp_server)

        smtp_server.server = smtp_form.server.data
        smtp_server.server_port = smtp_form.server_port.data if len(smtp_form.server_port.data) > 0 else None
        smtp_server.sender = smtp_form.sender.data
        smtp_server.use_authentication = smtp_form.use_authentication.data
        smtp_server.username = smtp_form.username.data
        if len(smtp_form.password.data) > 0:
            smtp_server.password = smtp_form.password.data
        smtp_server.secure_connection = smtp_form.secure_connection.data

        system_option.inventory_threads = admin_console_form.num_inventory_threads.data
        system_option.install_threads = admin_console_form.num_install_threads.data
        system_option.download_threads = admin_console_form.num_download_threads.data
        system_option.can_schedule = admin_console_form.can_schedule.data
        system_option.can_install = admin_console_form.can_install.data
        system_option.enable_email_notify = admin_console_form.enable_email_notify.data
        system_option.enable_inventory = admin_console_form.enable_inventory.data

        # The LDAP UI may be hidden if it is not supported.
        # In this case, the flag is not set.
        if not is_empty(admin_console_form.enable_ldap_auth.data):
            system_option.enable_ldap_auth = admin_console_form.enable_ldap_auth.data
            system_option.ldap_server_url = admin_console_form.ldap_server_url.data
            system_option.ldap_default_user_privilege = admin_console_form.ldap_default_user_privilege.data
            system_option.ldap_server_distinguished_names = admin_console_form.ldap_server_distinguished_names.data.strip()

        system_option.inventory_hour = admin_console_form.inventory_hour.data
        system_option.inventory_history_per_host = admin_console_form.inventory_history_per_host.data
        system_option.download_history_per_user = admin_console_form.download_history_per_user.data
        system_option.install_history_per_host = admin_console_form.install_history_per_host.data
        system_option.total_system_logs = admin_console_form.total_system_logs.data
        system_option.enable_default_host_authentication = admin_console_form.enable_default_host_authentication.data
        system_option.default_host_authentication_choice = admin_console_form.default_host_authentication_choice.data
        system_option.enable_cco_lookup = admin_console_form.enable_cco_lookup.data
        system_option.use_utc_timezone = admin_console_form.use_utc_timezone.data
        system_option.default_host_username = admin_console_form.default_host_username.data

        if len(admin_console_form.default_host_password.data) > 0:
            system_option.default_host_password = admin_console_form.default_host_password.data

        system_option.enable_user_credential_for_host = admin_console_form.enable_user_credential_for_host.data

        db_session.commit()

        return redirect(url_for('home'))
    else:

        admin_console_form.num_inventory_threads.data = system_option.inventory_threads
        admin_console_form.num_install_threads.data = system_option.install_threads
        admin_console_form.num_download_threads.data = system_option.download_threads
        admin_console_form.can_schedule.data = system_option.can_schedule
        admin_console_form.can_install.data = system_option.can_install
        admin_console_form.enable_email_notify.data = system_option.enable_email_notify
        admin_console_form.enable_ldap_auth.data = system_option.enable_ldap_auth
        admin_console_form.ldap_server_url.data = system_option.ldap_server_url
        admin_console_form.ldap_default_user_privilege.data = system_option.ldap_default_user_privilege
        admin_console_form.ldap_server_distinguished_names.data = system_option.ldap_server_distinguished_names
        admin_console_form.enable_inventory.data = system_option.enable_inventory
        admin_console_form.inventory_hour.data = system_option.inventory_hour
        admin_console_form.inventory_history_per_host.data = system_option.inventory_history_per_host
        admin_console_form.download_history_per_user.data = system_option.download_history_per_user
        admin_console_form.install_history_per_host.data = system_option.install_history_per_host
        admin_console_form.total_system_logs.data = system_option.total_system_logs
        admin_console_form.enable_default_host_authentication.data = system_option.enable_default_host_authentication
        admin_console_form.default_host_authentication_choice.data = system_option.default_host_authentication_choice
        admin_console_form.default_host_username.data = system_option.default_host_username
        admin_console_form.enable_cco_lookup.data = system_option.enable_cco_lookup
        admin_console_form.use_utc_timezone.data = system_option.use_utc_timezone
        admin_console_form.cco_lookup_time.data = get_datetime_string(system_option.cco_lookup_time)
        admin_console_form.enable_user_credential_for_host.data = system_option.enable_user_credential_for_host

        if not is_empty(system_option.default_host_password):
            admin_console_form.default_host_password_placeholder = 'Use Password on File'
        else:
            admin_console_form.default_host_password_placeholder = 'No Password Specified'

        if smtp_server is not None:
            smtp_form.server.data = smtp_server.server
            smtp_form.server_port.data = smtp_server.server_port
            smtp_form.sender.data = smtp_server.sender
            smtp_form.use_authentication.data = smtp_server.use_authentication
            smtp_form.username.data = smtp_server.username
            smtp_form.secure_connection.data = smtp_server.secure_connection
            if not is_empty(smtp_server.password):
                smtp_form.password_placeholder = 'Use Password on File'
            else:
                smtp_form.password_placeholder = 'No Password Specified'

        return render_template('admin/index.html',
                               admin_console_form=admin_console_form,
                               smtp_form=smtp_form,
                               system_option=SystemOption.get(db_session),
                               is_ldap_supported=is_ldap_supported())


class AdminConsoleForm(Form):
    num_inventory_threads = IntegerField('Number of Inventory Processes', [validators.NumberRange(min=2, max=50)])
    num_install_threads = IntegerField('Number of Installation Processes', [validators.NumberRange(min=2, max=100)])
    num_download_threads = IntegerField('Number of Software Download Processes', [validators.NumberRange(min=2, max=50)])
    can_schedule = HiddenField("Allow Users to Schedule Install")
    can_install = HiddenField("Allow Scheduled Installs to Run")
    enable_email_notify = HiddenField("Enable Email Notification")
    enable_inventory = HiddenField("Enable Software Inventory")
    inventory_hour = SelectField('Hour to Perform Software Inventory', coerce=int,
                                 choices=[(0, '12:00 AM'), (1, '01:00 AM'), (2, '02:00 AM'),
                                          (3, '03:00 AM'), (4, '04:00 AM'), (5, '05:00 AM'),
                                          (6, '06:00 AM'), (7, '07:00 AM'), (8, '08:00 AM'),
                                          (9, '09:00 AM'), (10, '10:00 AM'), (11, '11:00 AM'),
                                          (12, '12:00 PM'), (13, '01:00 PM'), (14, '02:00 PM'),
                                          (15, '03:00 PM'), (16, '04:00 PM'), (17, '05:00 PM'),
                                          (18, '06:00 PM'), (19, '07:00 PM'), (20, '08:00 PM'),
                                          (21, '09:00 PM'), (22, '10:00 PM'), (23, '11:00 PM')])
    inventory_history_per_host = IntegerField('Retrieval History Per Host', [validators.NumberRange(min=10, max=100)])
    install_history_per_host = IntegerField('Installation History Per Host', [validators.NumberRange(min=10, max=1000)])
    download_history_per_user = IntegerField('Software Download History Per User', [validators.NumberRange(min=10, max=100)])
    total_system_logs = IntegerField('Total System Logs', [validators.NumberRange(min=100, max=100000)])
    enable_default_host_authentication = HiddenField("Use Default Host Authentication")
    default_host_username = StringField('Default Host Username')
    default_host_password = PasswordField('Default Host Password')
    default_host_authentication_choice = \
        RadioField('Apply To',
                   choices=[(DefaultHostAuthenticationChoice.ALL_HOSTS, 'All Hosts'),
                            (DefaultHostAuthenticationChoice.HOSTS_WITH_NO_SPECIFIED_USERNAME_AND_PASSWORD,
                            'Hosts with no Specified Username and Password')])
    enable_ldap_auth = HiddenField("Enable LDAP")
    ldap_server_url = StringField('LDAP Server URL')
    ldap_default_user_privilege = SelectField('Grant User Privilege', [required()], coerce=str, choices=[('', '')])
    ldap_server_distinguished_names = StringField('Distinguished Names')
    enable_cco_lookup = HiddenField("Enable CCO Connection")
    cco_lookup_time = HiddenField("Last Retrieval")
    enable_user_credential_for_host = HiddenField("Use CSM Server User Credential")
    use_utc_timezone = HiddenField("Use UTC Time Zone")


class SMTPForm(Form):
    server = StringField('Outgoing SMTP Server')
    server_port = StringField('SMTP Server Port')
    sender = StringField('Sender Email Address')
    use_authentication = HiddenField("Server uses Authentication")
    username = StringField('Username')
    password = PasswordField('Password')
    secure_connection = SelectField('Secure Connection', coerce=str,
                                    choices=[(SMTPSecureConnection.SSL, SMTPSecureConnection.SSL),
                                             (SMTPSecureConnection.TLS, SMTPSecureConnection.TLS)])