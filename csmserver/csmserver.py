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

from flask import Flask
from flask import render_template
from flask import jsonify, abort, send_file
from flask import request, Response, redirect, url_for, make_response
from flask.ext.login import LoginManager, current_user
from flask.ext.login import login_user, login_required, logout_user  
from platform_matcher import get_platform, get_release, UNKNOWN

from werkzeug.contrib.fixers import ProxyFix

from sqlalchemy import or_, and_

from database import DBSession
from forms import HostForm 
from forms import JumpHostForm
from forms import LoginForm
from forms import UserForm
from forms import RegionForm
from forms import ServerForm 
from forms import ScheduleInstallForm
from forms import HostScheduleInstallForm
from forms import AdminConsoleForm
from forms import SMTPForm
from forms import PreferencesForm
from forms import ServerDialogForm
from forms import BrowseServerDialogForm
from forms import SoftwareProfileForm

from models import Host
from models import HostContext
from models import JumpHost
from models import InventoryJob
from models import ConnectionParam
from models import Log, logger 
from models import InventoryJobHistory
from models import InstallJob
from models import InstallJobHistory
from models import Region
from models import User
from models import Server
from models import SMTPServer
from models import SystemOption
from models import SystemVersion
from models import System
from models import Package
from models import Preferences
from models import SMUMeta
from models import SMUInfo
from models import DownloadJob
from models import DownloadJobHistory
from models import CSMMessage
from models import get_download_job_key_dict

from validate import is_connection_valid
from validate import is_reachable

from constants import InstallAction
from constants import JobStatus
from constants import PackageState
from constants import ServerType
from constants import UserPrivilege
from constants import ConnectionType
from constants import BUG_SEARCH_URL
from constants import get_log_directory
from constants import get_repository_directory
from constants import get_temp_directory
from constants import DefaultHostAuthenticationChoice

from common import get_last_successful_inventory_elapsed_time
from common import get_host_active_packages 
from common import fill_servers
from common import fill_dependencies
from common import fill_dependency_from_host_install_jobs
from common import fill_regions    
from common import fill_jump_hosts
from common import fill_custom_command_profiles
from common import get_custom_command_profile_by_id
from common import get_host
from common import get_host_list
from common import get_jump_host_by_id
from common import get_jump_host
from common import get_jump_host_list
from common import get_server
from common import get_server_by_id
from common import get_server_list
from common import get_region
from common import get_region_by_id
from common import get_region_list
from common import get_user
from common import get_user_by_id
from common import get_user_list
from common import get_smtp_server
from common import can_check_reachability
from common import can_retrieve_software
from common import can_install
from common import can_delete_install
from common import can_edit_install
from common import can_create_user
from common import can_edit
from common import can_delete
from common import can_create
from common import create_or_update_install_job
from common import create_download_jobs
from common import get_download_job_key
from common import get_last_successful_pre_upgrade_job
from common import create_or_update_host
from common import delete_host

from common import *

from filters import get_datetime_string
from filters import time_difference_UTC 
from filters import beautify_platform

from utils import get_file_list
from utils import make_url
from utils import trim_last_slash
from utils import is_empty
from utils import get_tarfile_file_list
from utils import comma_delimited_str_to_list
from utils import get_base_url 
from utils import is_ldap_supported
from utils import remove_extra_spaces
from utils import get_json_value
from utils import create_directory
from utils import create_temp_user_directory
from utils import make_file_writable
from utils import datetime_from_utc_to_local

from server_helper import get_server_impl
from wtforms.validators import Required

from smu_utils import get_validated_list
from smu_utils import get_missing_prerequisite_list
from smu_utils import get_download_info_dict
from smu_utils import get_platform_and_release
from smu_utils import SMU_INDICATOR

from smu_info_loader import SMUInfoLoader
from cisco_service.bsd_service import BSDServiceHandler
from cisco_service.bug_service import BugServiceHandler

from package_utils import get_target_software_package_list
from restful import restful_api

from views.exr_migrate import exr_migrate
from views.conformance import conformance
from views.tar_support import tar_support
from views.host_import import host_import
from views.custom_command import custom_command

from horizon.plugin_manager import PluginManager

import os
import stat
import io
import logging
import datetime
import filters
import collections
import shutil
import initialize
import zipfile

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

app.register_blueprint(restful_api)
app.register_blueprint(exr_migrate)
app.register_blueprint(conformance)
app.register_blueprint(tar_support)
app.register_blueprint(host_import)
app.register_blueprint(custom_command)

# Hook up the filters
filters.init(app)

app.secret_key = 'CSMSERVER'
    
# Use Flask-Login to track the current user in Flask's session.
login_manager = LoginManager()
login_manager.setup_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in.'


@login_manager.user_loader
def load_user(user_id):
    """Hook for Flask-Login to load a User instance from a user ID."""
    db_session = DBSession()
    return db_session.query(User).get(user_id)


@app.route('/')
@login_required
def home():
    db_session = DBSession()

    total_host_count = db_session.query(Host).count()
    total_region_count = db_session.query(Region).count()
    
    jump_hosts = get_jump_host_list(db_session)
    regions = get_region_list(db_session)
    servers = get_server_list(db_session)
    
    form = BrowseServerDialogForm(request.form)
    fill_servers(form.dialog_server.choices, get_server_list(DBSession()), False)

    return render_template('host/home.html', form=form, total_host_count=total_host_count, 
                           total_region_count=total_region_count, jump_hosts=jump_hosts, regions=regions,
                           servers=servers, build_date=get_build_date(), current_user=current_user)


@app.route('/api/get_host_platform_version/region/<int:region_id>')
@login_required
def get_host_platform_version(region_id):
    db_session = DBSession()
    
    if region_id == 0:
        hosts = db_session.query(Host)
    else:
        hosts = db_session.query(Host).filter(Host.region_id == region_id)
    
    host_dict = {}
    if hosts is not None:
        for host in hosts:
            platform = 'Unknown' if host.software_platform is None else host.software_platform
            software = 'Unknown' if host.software_version is None else host.software_version
              
            key = '{}={}'.format(platform, software)
            if key in host_dict:
                host_dict[key] += 1
            else:
                host_dict[key] = 1

    rows = []
    # key is a tuple ('4.2.3-asr9k', 1)
    for key in host_dict.items():
        row = {}
        info_array = key[0].split('=')
        row['platform'] = info_array[0]
        row['software'] = info_array[1]
        row['host_count'] = key[1]
        rows.append(row)
        
    return jsonify(**{'data': rows})


@app.route('/install_dashboard')
@login_required
def install_dashboard():
    db_session = DBSession()

    hosts = get_host_list(db_session)
    if hosts is None:
        abort(404)
            
    return render_template('host/install_dashboard.html', hosts=hosts) 


@app.route('/users/create', methods=['GET','POST'])
@login_required
def user_create():
    if not can_create_user(current_user):
        abort(401)
        
    form = UserForm(request.form)
    # Need to add the Required flag back as it is globally removed during user_edit()
    add_validator(form.password, Required) 
    
    if request.method == 'POST' and form.validate():
        db_session = DBSession()
        user = get_user(db_session, form.username.data)

        if user is not None:
            return render_template('user/edit.html', form=form, duplicate_error=True)
        
        user = User(
            username=form.username.data,
            password=form.password.data,
            privilege=form.privilege.data,
            fullname=form.fullname.data,
            email=form.email.data)
        
        user.preferences.append(Preferences())
        db_session.add(user)
        db_session.commit()
            
        return redirect(url_for('home'))
    else:
        # Default to Active
        form.active.data = True
        return render_template('user/edit.html', form=form)


@app.route('/users/edit', methods=['GET','POST'])
@login_required
def current_user_edit(): 
    return user_edit(current_user.username)


@app.route('/users/<username>/edit', methods=['GET','POST'])
@login_required
def user_edit(username):
    db_session = DBSession()
    
    user = get_user(db_session, username)
    if user is None:
        abort(404)
        
    form = UserForm(request.form)
            
    if request.method == 'POST' and form.validate():

        if len(form.password.data) > 0:
            user.password = form.password.data
        
        user.privilege = form.privilege.data
        user.fullname = form.fullname.data
        user.email = form.email.data
        user.active = form.active.data
        db_session.commit()
        
        return redirect(url_for('home'))
    else:
        form.username.data = user.username
        # Remove the Required flag so validation won't fail.  In edit mode, it is okay
        # not to provide the password.  In this case, the password on file is used.      
        remove_validator(form.password, Required) 
        
        form.privilege.data = user.privilege             
        form.fullname.data = user.fullname
        form.email.data = user.email
        form.active.data = user.active

    return render_template('user/edit.html', form=form)


@app.route('/users/')
@login_required
def user_list():
    db_session = DBSession()

    users = get_user_list(db_session)
    if users is None:
        abort(404)
     
    if current_user.privilege == UserPrivilege.ADMIN:    
        return render_template('user/index.html', users=users)
    
    return render_template('user/not_authorized.html', user=current_user)


@app.route('/users/<username>/delete/', methods=['DELETE'])
@login_required
def user_delete(username):
    db_session = DBSession()

    user = get_user(db_session, username)
    if user is None:
        abort(404)
     
    db_session.delete(user)
    db_session.commit()
        
    return jsonify({'status': 'OK'})


@app.route('/login/', methods=['GET', 'POST'])
def login():
    
    form = LoginForm(request.form)
    error_message = None
    
    if request.method == 'POST' and form.validate():
        username = form.username.data.strip()
        password = form.password.data.strip()
        
        db_session = DBSession()

        user, authenticated = \
            User.authenticate(db_session.query, username, password)
            
        if authenticated:
            login_user(user)
            
            # record the base URL
            try:
                system_option = SystemOption.get(db_session)
                system_option.base_url = get_base_url(request.url)
                db_session.commit()
            except:
                logger.exception('login() hit exception')
            
            # Certain admin features (Admin Console/Create or Edit User require 
            # re-authentication. The return_url indicates which admin feature the 
            # user wants to access.
            return_url = get_return_url(request)
            if return_url is None:              
                return redirect(request.args.get("next") or url_for('home'))
            else:
                return redirect(url_for(return_url))
        else:
            error_message = 'Your user name or password is incorrect.  \
                             Re-enter them again or contact your system administrator.'
 
    # Fill the username if the user is still logged in.
    username = get_username(current_user)
    if username is not None:
        form.username.data = username
        
    return render_template('user/login.html', form=form, error_message=error_message, username=username)


def get_username(current_user):
    """
    Return the current username.  If the user already logged out, return None
    """
    try:
        return current_user.username
    except:
        return None


@app.route('/logout/')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/api/get_region_host_count/region/<int:region_id>')
@login_required
def get_region_host_count(region_id):
    db_session = DBSession()
    
    if region_id == 0:
        count = db_session.query(Host).count()
    else:
        count = db_session.query(Host).filter(Host.region_id == region_id).count()
        
    return jsonify(**{'data': [{'region_host_count': count}]})
    

@app.route('/api/get_region_name/region/<int:region_id>')
@login_required
def get_region_name(region_id):
    region_name = 'ALL'
    db_session = DBSession()
    
    if region_id > 0:
        region = get_region_by_id(db_session, region_id)
        if region is not None:
            region_name = region.name
        
    return jsonify(**{'data': [{'region_name': region_name}]})
        
    
@app.route('/api/get_managed_hosts/region/<int:region_id>')
@login_required
def get_managed_hosts(region_id):

    rows = []
    db_session = DBSession()

    if region_id == 0:
        hosts = db_session.query(Host)
    else:
        hosts = db_session.query(Host).filter(Host.region_id == region_id)
    
    if hosts is not None:
        for host in hosts:
            row = {}
            row['hostname'] = host.hostname
            row['region'] = '' if host.region is None else host.region.name

            if len(host.connection_param) > 0:
                row['host_or_ip'] = host.connection_param[0].host_or_ip
                row['platform'] = host.platform

                if host.software_version is not None:
                    row['software'] = host.software_platform + ' (' + host.software_version + ')'
                else:
                    row['software'] = 'Unknown'

                inventory_job = host.inventory_job[0]
                if inventory_job is not None and inventory_job.last_successful_time is not None:
                    row['last_successful_retrieval'] = get_last_successful_inventory_elapsed_time(host)
                    row['inventory_status'] = inventory_job.status
                else:
                    row['last_successful_retrieval'] = ''
                    row['inventory_status'] = ''

                rows.append(row)
            else:
                logger.error('Host %s has no connection information.', host.hostname)
    
    return jsonify(**{'data': rows})


@app.route('/api/get_managed_host_details/region/<int:region_id>')
@login_required
def get_managed_host_details(region_id):
    rows = []   
    db_session = DBSession()

    if region_id == 0:
        hosts = db_session.query(Host)
    else:
        hosts = db_session.query(Host).filter(Host.region_id == region_id)
    
    if hosts is not None:
        for host in hosts:
            row = {} 
            row['hostname'] = host.hostname
            row['platform'] = host.platform
            row['software'] = (host.software_platform if host.software_platform is not None else UNKNOWN) + ' (' + \
                              (host.software_version if host.software_version is not None else UNKNOWN) + ')'

            if len(host.connection_param) > 0:
                connection_param = host.connection_param[0]
                row['connection'] = connection_param.connection_type
                row['host_or_ip'] = connection_param.host_or_ip
                row['port_number'] = 'Default' if is_empty(connection_param.port_number) else connection_param.port_number

                if not is_empty(connection_param.jump_host):
                    row['jump_host'] = connection_param.jump_host.hostname
                else:
                    row['jump_host'] = ''

                row['username'] = connection_param.username

                rows.append(row)
            else:
                logger.error('Host %s has no connection information.', host.hostname)
    
    return jsonify(**{'data': rows})


@app.route('/api/acknowledge_csm_message', methods=['POST'])
def api_acknowledge_csm_message():
    username = request.form['username']      
    password = request.form['password']
    
    db_session = DBSession()
     
    user, authenticated = \
        User.authenticate(db_session.query, username, password)
            
    if authenticated:  
        if len(user.csm_message) == 0:
            user.csm_message.append(CSMMessage(acknowledgment_date=datetime.date.today() ))
        else:                
            user.csm_message[0].acknowledgment_date=datetime.date.today() 
                
        db_session.commit()
        
    return jsonify({'status': 'OK'})


@app.route('/api/get_csm_message', methods=['POST'])
def api_get_csm_message():
    rows = [] 

    username = request.form['username']      
    password = request.form['password']
    
    db_session = DBSession()
     
    user, authenticated = \
        User.authenticate(db_session.query, username, password)
            
    if authenticated:  
        # if user.privilege == UserPrivilege.ADMIN: 
        csm_messages = SMUInfoLoader.get_cco_csm_messages()
        if len(csm_messages) > 0:
            acknowledgment_date = datetime.datetime(2000, 1, 1)                 
            if len(user.csm_message) > 0:
                acknowledgment_date = user.csm_message[0].acknowledgment_date
                
            # csm_messages returns a dictionary keyed by a token (e.g. @12/01/01@Admin,Operator) and message
            readers = [ UserPrivilege.ADMIN, UserPrivilege.NETWORK_ADMIN, UserPrivilege.OPERATOR, UserPrivilege.VIEWER]
            for csm_message in csm_messages:
                tokens = csm_message['token'].split('@')
                date = tokens[0]
                if len(tokens) == 2:
                    readers = tokens[1].split(',')
                
                if user.privilege in readers:
                    message = csm_message['message']
                    try:                       
                        delta = datetime.datetime.strptime(date, "%Y/%m/%d") - acknowledgment_date                       
                        if delta.days > 0:
                            rows.append({'date': date, 'message': message.replace("\n", "<br>")})
                    except:
                        logger.exception('api_get_csm_message() hit exception')
    
    return jsonify(**{'data': rows})


@app.route('/hosts/')
@login_required
def host_list():
    db_session = DBSession()

    hosts = get_host_list(db_session)
    if hosts is None:
        abort(404)
            
    return render_template('host/index.html', hosts=hosts)


@app.route('/hosts/create/', methods=['GET', 'POST'])
@login_required
def host_create():    
    if not can_create(current_user):
        abort(401)
        
    form = HostForm(request.form) 
    
    fill_jump_hosts(form.jump_host.choices)
    fill_regions(form.region.choices)
    
    if request.method == 'POST' and form.validate():
        db_session = DBSession()
        try:
            host = get_host(db_session, form.hostname.data)
            if host is not None:
                return render_template('host/edit.html', form=form, duplicate_error=True)

            host = create_or_update_host(db_session=db_session, hostname=form.hostname.data, region_id=form.region.data,
                                         roles=form.roles.data, connection_type=form.connection_type.data,
                                         host_or_ip=form.host_or_ip.data, username=form.username.data,
                                         password=form.password.data, enable_password=form.enable_password.data,
                                         port_number=form.port_number.data, jump_host_id=form.jump_host.data,
                                         created_by=current_user.username)

        finally:
            db_session.rollback()
            
        return redirect(url_for('home'))

    return render_template('host/edit.html', form=form)


@app.route('/hosts/<hostname>/edit/', methods=['GET', 'POST'])
@login_required
def host_edit(hostname):        
    db_session = DBSession()
    
    host = get_host(db_session, hostname)
    if host is None:
        abort(404)
        
    form = HostForm(request.form)
    fill_jump_hosts(form.jump_host.choices)
    fill_regions(form.region.choices)

    if request.method == 'POST' and form.validate():
        if not can_edit(current_user):
            abort(401)
        
        if hostname != form.hostname.data and get_host(db_session, form.hostname.data) is not None:
            return render_template('host/edit.html', form=form, duplicate_error=True)
        
        host.hostname = form.hostname.data
        host.region_id = form.region.data if form.region.data > 0 else None
        host.roles = remove_extra_spaces(form.roles.data) 
        
        connection_param = host.connection_param[0]
        # could have multiple IPs, separated by comma
        connection_param.host_or_ip = remove_extra_spaces(form.host_or_ip.data) 
        connection_param.username = form.username.data
        if len(form.password.data) > 0:
            connection_param.password = form.password.data

        if len(form.enable_password.data) > 0:
            connection_param.enable_password = form.enable_password.data

        connection_param.jump_host_id = form.jump_host.data if form.jump_host.data > 0 else None
        connection_param.connection_type = form.connection_type.data
        # could have multiple ports, separated by comma
        connection_param.port_number = remove_extra_spaces(form.port_number.data)
        db_session.commit()
        
        return_url = get_return_url(request, 'home')
        if return_url is None:
            return redirect(url_for('home'))
        else:
            return redirect(url_for(return_url, hostname=hostname))
    else:
        # Assign the values to form fields
        form.hostname.data = host.hostname
        form.region.data = host.region_id
        form.roles.data = host.roles
        form.host_or_ip.data = host.connection_param[0].host_or_ip
        form.username.data = host.connection_param[0].username
        form.jump_host.data = host.connection_param[0].jump_host_id
        form.connection_type.data = host.connection_param[0].connection_type
        form.port_number.data = host.connection_param[0].port_number
        if not is_empty(host.connection_param[0].password):
            form.password_placeholder = 'Use Password on File'
        else:
            form.password_placeholder = 'No Password Specified'

        if not is_empty(host.connection_param[0].enable_password):
            form.enable_password_placeholder = 'Use Password on File'
        else:
            form.enable_password_placeholder = 'No Password Specified'

        return render_template('host/edit.html', form=form)

   
@app.route('/hosts/<hostname>/delete/', methods=['DELETE'])
@login_required
def host_delete(hostname):
    if not can_delete(current_user):
        abort(401)

    db_session = DBSession()

    try:
        delete_host(db_session, hostname)
    except:
        abort(404)
        
    return jsonify({'status': 'OK'})


@app.route('/jump_hosts/')
@login_required
def jump_host_list():
    db_session = DBSession()
  
    hosts = get_jump_host_list(db_session)
    if hosts is None:
        abort(404)
            
    return render_template('jump_host/index.html', hosts=hosts)


@app.route('/jump_hosts/create/', methods=['GET', 'POST'])
@login_required
def jump_host_create():
    if not can_create(current_user):
        abort(401)
        
    form = JumpHostForm(request.form)
    
    if request.method == 'POST' and form.validate():           
        db_session = DBSession()       
        host = get_jump_host(db_session, form.hostname.data)
        if host is not None:
            return render_template('jump_host/edit.html', form=form, duplicate_error=True)
        
        host = JumpHost(
            hostname=form.hostname.data,
            host_or_ip=form.host_or_ip.data,
            username=form.username.data,
            password=form.password.data,
            connection_type=form.connection_type.data,
            port_number=form.port_number.data,
            created_by=current_user.username)
          
        db_session.add(host)
        db_session.commit() 
            
        return redirect(url_for('home'))
                
    return render_template('jump_host/edit.html', form=form)


@app.route('/jump_hosts/<hostname>/edit/', methods=['GET', 'POST'])
@login_required
def jump_host_edit(hostname):        
    db_session = DBSession()
    
    host = get_jump_host(db_session, hostname)
    if host is None:
        abort(404)
        
    form = JumpHostForm(request.form, host)

    if request.method == 'POST' and form.validate():
        if not can_edit(current_user):
            abort(401)
        
        if hostname != form.hostname.data and get_jump_host(db_session, form.hostname.data) is not None:
            return render_template('jump_host/edit.html', form=form, duplicate_error=True)
        
        host.hostname = form.hostname.data
        host.host_or_ip = form.host_or_ip.data
        host.username = form.username.data
        if len(form.password.data) > 0:
            host.password = form.password.data
        host.connection_type = form.connection_type.data
        host.port_number = form.port_number.data
        db_session.commit()
        
        return redirect(url_for('home'))
    else:
        # Assign the values to form fields
        form.hostname.data = host.hostname
        form.host_or_ip.data = host.host_or_ip
        form.username.data = host.username
        form.connection_type.data = host.connection_type
        form.port_number.data = host.port_number
        if not is_empty(host.password):
            form.password_placeholder = 'Use Password on File'
        else:
            form.password_placeholder = 'No Password Specified'

        return render_template('jump_host/edit.html', form=form)


@app.route('/jump_hosts/<hostname>/delete/', methods=['DELETE'])
@login_required
def jump_host_delete(hostname):
    if not can_delete(current_user):
        abort(401)
        
    db_session = DBSession()
    
    host = get_jump_host(db_session, hostname)
    if host is None:
        abort(404)
        
    db_session.delete(host)
    db_session.commit()
        
    return jsonify({'status': 'OK'})


@app.route('/servers/create/', methods=['GET', 'POST'])
@login_required
def server_create():
    if not can_create(current_user):
        abort(401)
        
    form = ServerForm(request.form)
    
    if request.method == 'POST' and form.validate():          
        db_session = DBSession()        
        server = get_server(db_session, form.hostname.data)
        if server is not None:
            return render_template('server/edit.html', form=form, duplicate_error=True) 
        
        server = Server(
            hostname=form.hostname.data,
            server_type=form.server_type.data,
            server_url=trim_last_slash(form.server_url.data), 
            username=form.username.data,
            password=form.password.data,
            vrf=form.vrf.data,
            server_directory=trim_last_slash(form.server_directory.data),
            created_by=current_user.username)
            
        db_session.add(server)
        db_session.commit()
            
        return redirect(url_for('home'))

    return render_template('server/edit.html', form=form)


@app.route('/servers/<hostname>/edit/', methods=['GET', 'POST'])
@login_required
def server_edit(hostname):        
    db_session = DBSession()
    
    server = get_server(db_session, hostname)
    if server is None:
        abort(404)
        
    form = ServerForm(request.form)

    if request.method == 'POST' and form.validate():
        if not can_edit(current_user):
            abort(401)
        
        if hostname != form.hostname.data and get_server(db_session, form.hostname.data) is not None:
            return render_template('server/edit.html', form=form, duplicate_error=True)
        
        server.hostname = form.hostname.data
        server.server_type = form.server_type.data
        server.server_url = trim_last_slash(form.server_url.data)
        server.vrf = form.vrf.data
        server.username = form.username.data
        if len(form.password.data) > 0:
            server.password = form.password.data
        server.server_directory = trim_last_slash(form.server_directory.data)
        db_session.commit()
        
        return redirect(url_for('home'))
    else:
        # Assign the values to form fields
        form.hostname.data = server.hostname
        form.server_type.data = server.server_type
        form.server_url.data = server.server_url
        form.username.data = server.username
        form.vrf.data = server.vrf
        # In Edit mode, make the password field not required
        form.server_directory.data = server.server_directory
        
        return render_template('server/edit.html', form=form)
    

@app.route('/servers/<hostname>/delete/', methods=['DELETE'])
@login_required
def server_delete(hostname):
    if not can_delete(current_user):
        abort(401)
        
    db_session = DBSession()

    server = get_server(db_session, hostname)
    if server is None:
        abort(404)
    
    if len(server.regions) == 0:
        db_session.delete(server)
        db_session.commit()
        
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


@app.route('/regions/create/', methods=['GET', 'POST'])
@login_required
def region_create():
    if not can_create(current_user):
        abort(401)
        
    form = RegionForm(request.form)
    
    if request.method == 'POST' and form.validate():
            
        db_session = DBSession()        
        region = get_region(db_session, form.region_name.data)
                
        if region is not None:
            return render_template('region/edit.html', form=form, duplicate_error=True)   
            
        region = Region(
            name=form.region_name.data,
            created_by=current_user.username)
        
        server_id_list = request.form.getlist('selected-servers')
        for server_id in server_id_list:
            server = get_server_by_id(db_session, server_id)
            if server is not None:
                region.servers.append(server)

        db_session.add(region)
        db_session.commit()   
                   
        return redirect(url_for('home'))
    
    return render_template('region/edit.html', form=form)


@app.route('/regions/<region_name>/edit/', methods=['GET', 'POST'])
@login_required
def region_edit(region_name):       
    db_session = DBSession()
    
    region = get_region(db_session, region_name)
    if region is None:
        abort(404)
        
    form = RegionForm(request.form)

    if request.method == 'POST' and form.validate():
        if not can_edit(current_user):
            abort(401)
        
        if region_name != form.region_name.data and get_region(db_session, form.region_name.data) is not None:
            return render_template('region/edit.html', form=form, duplicate_error=True)
        
        region.name = form.region_name.data
        region.servers = []
        server_id_list = request.form.getlist('selected-servers')
        for server_id in server_id_list:
            server = get_server_by_id(db_session, server_id)
            if server is not None:
                region.servers.append(server)
        
        db_session.commit()
        
        return redirect(url_for('home'))
    else:
        form.region_name.data = region.name

        return render_template('region/edit.html', form=form, region=region)


@app.route('/regions/<region_name>/delete/', methods=['DELETE'])
@login_required
def region_delete(region_name):
    if not can_delete(current_user):
        abort(401)
        
    db_session = DBSession()

    region = get_region(db_session, region_name)
    if region is None:
        abort(404)
     
    # Older version of db does not perform check on
    # foreign key constrain, so do it programmatically here.
    count = db_session.query(Host).filter(
        Host.region_id == region.id).count()

    if count == 0:
        db_session.delete(region)
        db_session.commit()
        
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


def add_validator(field, validator_class):
    validators = field.validators
    for v in validators:
        if isinstance(v, validator_class):
            return
        
    validators.append(validator_class())


def remove_validator(field, validator_class):
    validators = field.validators
    for v in validators:
        if isinstance(v, validator_class):
            validators.remove(v) 


@app.route('/api/hosts/<hostname>/last_successful_inventory_elapsed_time/')
@login_required 
def api_get_last_successful_inventory_elapsed_time(hostname):
    db_session = DBSession()
    host = get_host(db_session, hostname)
    if host is None:
        abort(404)
    
    return jsonify(**{'data': [
        {'last_successful_inventory_elapsed_time': get_last_successful_inventory_elapsed_time(host),
         'status': host.inventory_job[0].status}
    ]})



@app.route('/api/hosts/<hostname>/packages/<package_state>', methods=['GET','POST'])
@login_required
def api_get_host_dashboard_packages(hostname, package_state):
    db_session = DBSession()
    host = get_host(db_session, hostname)

    rows = []       
    if host is not None:
        # It is possible that package_state contains a commas delimited state list.
        # In this case, the union of those packages will be used.
        package_states = package_state.split(',')
        packages = []
        for package_state in package_states:
            packages_list = db_session.query(Package).filter(
                and_(Package.host_id == host.id, Package.state == package_state)). order_by(Package.name).all()
            if len(packages_list) > 0:
                packages.extend(packages_list)
            
        has_module_packages = False
        for package in packages:        
            if len(package.modules_package_state) > 0:
                has_module_packages = True
                break
            
        if has_module_packages:
            module_package_dict = {}
            
            # Format it from module, then packages
            for package in packages:
                package_name = package.name if package.location is None else package.location + ':' + package.name
                for modules_package_state in package.modules_package_state:
                    module = modules_package_state.module_name
                    if module in module_package_dict:
                        module_package_dict[module].append(package_name)
                    else:
                        package_list = []
                        package_list.append(package_name)
                        module_package_dict[module] = package_list
            
            sorted_dict = collections.OrderedDict(sorted(module_package_dict.items()))
            
            for module in sorted_dict:
                package_list = sorted_dict[module]
                rows.append({'package': module})
                for package_name in package_list:  
                    rows.append({'package': ('&nbsp;' * 7) + package_name})
            
        else:
            for package in packages:
                rows.append({'package': package.name if package.location is None else package.location + ':' + package.name})

    return jsonify(**{'data': rows})


@app.route('/api/hosts/<hostname>/scheduled_installs', methods=['GET','POST'])
@login_required
def api_get_host_dashboard_scheduled_install(hostname):
    """
    Returns scheduled installs for a host in JSON format.
    """
    db_session = DBSession()
    host = get_host(db_session, hostname)
    
    rows = []       
    if host is not None and len(host.install_job) > 0:
        for install_job in host.install_job:
            row = {}
            row['hostname'] = host.hostname
            row['install_job_id'] = install_job.id
            row['install_action'] = install_job.install_action
            row['scheduled_time'] = install_job.scheduled_time
            row['session_log'] = install_job.session_log
            row['status'] = install_job.status

            rows.append(row)
            
    return jsonify(**{'data': rows})


@app.route('/api/hosts/<hostname>/host_dashboard/cookie', methods=['GET', 'POST'])
@login_required
def api_get_host_dashboard_cookie(hostname):
    db_session = DBSession()
    host = get_host(db_session, hostname)

    rows = []
    if host is not None:
        system_option = SystemOption.get(db_session)
        row = {}
        connection_param = host.connection_param[0]
        row['hostname'] = host.hostname
        row['region'] = host.region.name if host.region is not None else 'Unknown'
        row['roles'] = host.roles
        row['platform'] = host.platform
        row['software_platform'] = host.software_platform
        row['software_version'] = host.software_version
        row['host_or_ip'] = connection_param.host_or_ip
        row['username'] = connection_param.username
        row['connection'] = connection_param.connection_type
        row['port_number'] = connection_param.port_number
        row['created_by'] = host.created_by
        
        if connection_param.jump_host is not None:
            row['jump_host'] = connection_param.jump_host.hostname
            
        # Last inventory successful time
        inventory_job = host.inventory_job[0]
        row['last_successful_inventory_elapsed_time'] = get_last_successful_inventory_elapsed_time(host)
        row['last_successful_inventory_time'] = inventory_job.last_successful_time
        row['status'] = inventory_job.status
        
        install_job_history_count = 0
        if host is not None:
            install_job_history_count = db_session.query(InstallJobHistory).count()
        
        row['last_install_job_history_count'] = install_job_history_count
        row['can_schedule'] = system_option.can_schedule
        rows.append(row)
    
    return jsonify(**{'data': rows})


@app.route('/api/hosts/<hostname>/install_job_history', methods=['GET'])
@login_required
def api_get_host_dashboard_install_job_history(hostname):
    rows = [] 
    db_session = DBSession()
    
    host = get_host(db_session, hostname)
    if host is not None:  
        record_limit = request.args.get('record_limit')
        if record_limit is None or record_limit.lower() == 'all':  
            install_jobs = db_session.query(InstallJobHistory).filter(InstallJobHistory.host_id == host.id). \
                order_by(InstallJobHistory.created_time.desc())
        else:  
            install_jobs = db_session.query(InstallJobHistory).filter(InstallJobHistory.host_id == host.id). \
                order_by(InstallJobHistory.created_time.desc()).limit(record_limit)

        return jsonify(**get_install_job_json_dict(install_jobs))
    
    return jsonify(**{'data': rows})


@app.route('/api/hosts/<hostname>/software_inventory_history', methods=['GET'])
@login_required
def api_get_host_dashboard_software_inventory_history(hostname):
    rows = [] 
    db_session = DBSession()
    
    host = get_host(db_session, hostname)
    if host is not None:  
        record_limit = request.args.get('record_limit')
        if record_limit is None or record_limit.lower() == 'all':  
            inventory_jobs = db_session.query(InventoryJobHistory).filter(InventoryJobHistory.host_id == host.id). \
                order_by(InventoryJobHistory.created_time.desc())
        else:  
            inventory_jobs = db_session.query(InventoryJobHistory).filter(InventoryJobHistory.host_id == host.id). \
                order_by(InventoryJobHistory.created_time.desc()).limit(record_limit)

        return jsonify(**get_inventory_job_json_dict(inventory_jobs))
    
    return jsonify(**{'data': rows})


def get_inventory_job_json_dict(inventory_jobs):
    rows = []    
    for inventory_job in inventory_jobs:
        row = {}
        row['hostname'] = inventory_job.host.hostname
        row['status'] = inventory_job.status
        row['status_time'] = inventory_job.status_time  
        row['elapsed_time'] = time_difference_UTC(inventory_job.status_time)
        row['inventory_job_id'] = inventory_job.id
            
        if inventory_job.session_log is not None:
            row['session_log'] = inventory_job.session_log
             
        if inventory_job.trace is not None:
            row['trace'] = inventory_job.id
                  
        rows.append(row)
       
    return {'data': rows}


@app.route('/api/install_scheduled/')
@login_required
def api_get_install_scheduled():
    db_session = DBSession()
    
    install_jobs = db_session.query(InstallJob).filter(
        (InstallJob.install_action is not None),
        and_(InstallJob.status == None))

    return jsonify(**get_install_job_json_dict(install_jobs))


@app.route('/api/install_in_progress/')
@login_required
def api_get_install_in_progress():
    db_session = DBSession()    
    install_jobs = db_session.query(InstallJob).filter(and_(
        InstallJob.status != None,
        InstallJob.status != JobStatus.FAILED))

    return jsonify(**get_install_job_json_dict(install_jobs))


@app.route('/api/install_failed/')
@login_required
def api_get_install_failed():
    db_session = DBSession()   
    install_jobs = db_session.query(InstallJob).filter(InstallJob.status == JobStatus.FAILED)

    return jsonify(**get_install_job_json_dict(install_jobs))


def get_download_job_status(download_job_key_dict, install_job, dependency_status):
    num_pending_downloads = 0
    num_failed_downloads = 0
    is_pending_download = False

    pending_downloads = install_job.pending_downloads.split(',')
    for filename in pending_downloads:
        download_job_key = get_download_job_key(install_job.user_id, filename, install_job.server_id, install_job.server_directory)
        if download_job_key in download_job_key_dict:
            download_job = download_job_key_dict[download_job_key]
            if download_job.status == JobStatus.FAILED:
                num_failed_downloads += 1
            else:
                num_pending_downloads += 1
            is_pending_download = True

    if is_pending_download:
        job_status = "({} pending".format(num_pending_downloads)
        if num_failed_downloads > 0:
            job_status = "{},{} failed)".format(job_status, num_failed_downloads)
        else:
            job_status = "{})".format(job_status)
            
        # job_status = '(Failed)' if is_download_failed else ''
        download_url = '<a href="' + url_for('download_dashboard') + '">Pending Download ' + job_status + '</a>'
        if len(dependency_status) > 0:
            dependency_status = '{}<br/>{}'.format(dependency_status, download_url)
        else:
            dependency_status = download_url
            
    return dependency_status
                        

def get_install_job_json_dict(install_jobs):
    """
    install_jobs is a list of install_job instances from the install_job or install_job_history table.
    Schema in the install_job_history table is a superset of the install_job table.
    """
    download_job_key_dict = get_download_job_key_dict()
    rows = []    
    for install_job in install_jobs:
        if isinstance(install_job, InstallJob) or isinstance(install_job, InstallJobHistory):
            row = {}
            row['install_job_id'] = install_job.id
            row['hostname'] = install_job.host.hostname
            row['dependency'] = '' if install_job.dependency is None else 'Another Installation'
            row['install_action'] = install_job.install_action
            row['scheduled_time'] = install_job.scheduled_time

            # Retrieve the pending download status of the scheduled download job.
            # The install job has not been started if its status is None.
            if install_job.status is None:
                row['dependency'] = get_download_job_status(download_job_key_dict, install_job, row['dependency'])

            row['start_time'] = install_job.start_time
            row['packages'] = install_job.packages
                           
            if isinstance(install_job, InstallJob):
                row['server_id'] = install_job.server_id
                row['server_directory'] = install_job.server_directory
                row['user_id'] = install_job.user_id
            
            row['status'] = install_job.status
            row['status_time'] = install_job.status_time               
            row['created_by'] = install_job.created_by
            
            if install_job.session_log is not None:
                row['session_log'] = install_job.session_log
                
            if install_job.trace is not None:
                row['trace'] = install_job.id
                  
            rows.append(row)
       
    return {'data': rows}


@app.route('/api/get_files_from_csm_repository/')
@login_required
def get_files_from_csm_repository():
    rows = []
    file_list = get_file_list(get_repository_directory())
    
    for filename in file_list:
        if filename.endswith('.tar'):
            statinfo = os.stat(get_repository_directory() + filename)
            row = {}
            row['image_name'] = filename
            row['image_size'] = str(statinfo.st_size)
            row['downloaded_time'] = datetime.datetime.fromtimestamp(statinfo.st_mtime).strftime("%m/%d/%Y %I:%M %p")
            rows.append(row)
    
    return jsonify(**{'data': rows})


@app.route('/api/image/<image_name>/delete/', methods=['DELETE'])
@login_required  
def api_delete_image_from_repository(image_name):
    if current_user.privilege != UserPrivilege.ADMIN and current_user.privilege != UserPrivilege.NETWORK_ADMIN:
        abort(401)
    
    tar_image_path = get_repository_directory() + image_name
    file_list = get_tarfile_file_list(tar_image_path)
    for filename in file_list:
        try:
            os.remove(get_repository_directory() + filename) 
        except:
            pass
       
    try:
        os.remove(tar_image_path) 
        os.remove(tar_image_path + '.size')
    except:
        logger.exception('api_delete_image_from_repository() hit exception')
        return jsonify({'status': 'Failed'})
    
    return jsonify({'status': 'OK'})

    
@app.route('/api/download_scheduled/')
@login_required
def api_get_download_scheduled():  
    db_session = DBSession()
    download_jobs = db_session.query(DownloadJob).filter(DownloadJob.status == None)

    return jsonify(**get_download_job_json_dict(db_session, download_jobs))


@app.route('/api/download_in_progress/')
@login_required
def api_get_download_in_progress():
    db_session = DBSession()    
    download_jobs = db_session.query(DownloadJob).filter(and_(
    DownloadJob.status != None,
    DownloadJob.status != JobStatus.FAILED) )

    return jsonify(**get_download_job_json_dict(db_session, download_jobs))


@app.route('/api/download_failed/')
@login_required
def api_get_download_failed():
    db_session = DBSession()   
    download_jobs = db_session.query(DownloadJob).filter(DownloadJob.status == JobStatus.FAILED)

    return jsonify(**get_download_job_json_dict(db_session, download_jobs))


@app.route('/api/download_completed/')
@login_required
def api_get_download_completed():
    db_session = DBSession()

    record_limit = request.args.get('record_limit')

    if record_limit is None or record_limit.lower() == 'all':   
        download_jobs = db_session.query(DownloadJobHistory).filter(DownloadJobHistory.status == JobStatus.COMPLETED). \
            order_by(DownloadJobHistory.status_time.desc())
    else:  
        download_jobs = db_session.query(DownloadJobHistory).filter(DownloadJobHistory.status == JobStatus.COMPLETED). \
            order_by(DownloadJobHistory.status_time.desc()).limit(record_limit)

    return jsonify(**get_download_job_json_dict(db_session, download_jobs))


@app.route('/api/download_dashboard/cookie')
@login_required
def api_get_download_dashboard_cookie():
    db_session = DBSession()

    completed_download_job_count = db_session.query(DownloadJobHistory).filter(
        DownloadJobHistory.status == JobStatus.COMPLETED).count()
    
    return jsonify(**{'data': [{'last_completed_download_job_count': completed_download_job_count}]})


def get_download_job_json_dict(db_session, download_jobs):
    rows = []    
    for download_job in download_jobs:
        if isinstance(download_job, DownloadJob) or isinstance(download_job, DownloadJobHistory):
            row = {}
            row['download_job_id'] = download_job.id
            row['image_name'] = download_job.cco_filename 
            row['scheduled_time'] = download_job.scheduled_time
            
            server = get_server_by_id(db_session, download_job.server_id)
            if server is not None:
                row['server_repository'] = server.hostname
                if not is_empty(download_job.server_directory):
                    row['server_repository'] = row['server_repository'] + \
                                               '<br><span style="color: Gray;"><b>Sub-directory:</b></span> ' + \
                                               download_job.server_directory
            else:
                row['server_repository'] = 'Unknown'
                
            row['status'] = download_job.status
            row['status_time'] = download_job.status_time               
            row['created_by'] = download_job.created_by
            
            if download_job.trace is not None:
                row['trace'] = download_job.id
                  
            rows.append(row)
       
    return {'data': rows}


@app.route('/api/resubmit_download_jobs/')
@login_required
def api_resubmit_download_jobs():
    if not can_install(current_user):
        abort(401)
     
    user_id = request.args.get("user_id")   
    server_id = request.args.get("server_id")
    server_directory = request.args.get("server_directory")
    
    db_session = DBSession()   
    download_jobs = db_session.query(DownloadJob).filter(and_(DownloadJob.user_id == user_id, 
        DownloadJob.server_id == server_id, DownloadJob.server_directory == server_directory))
    
    for download_job in download_jobs:
        download_job.status = None
        download_job.status_time = None        
    db_session.commit()
    
    return jsonify({'status': 'OK'})


@app.route('/resubmit_download_job/<int:id>/', methods=['POST'])
@login_required
def resubmit_download_job(id):
    if not can_install(current_user):
        abort(401)
    
    db_session = DBSession()
    
    download_job = db_session.query(DownloadJob).filter(DownloadJob.id == id).first()
    if download_job is None:
        abort(404)   

    try: 
        # Download jobs that are in progress cannot be deleted.
        download_job.status = None
        download_job.status_time = None        
        db_session.commit()
        
        return jsonify({'status': 'OK'})

    except:  
        logger.exception('resubmit_download_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@app.route('/delete_download_job/<int:id>/', methods=['DELETE'])
@login_required
def delete_download_job(id):
    if not can_delete_install(current_user):
        abort(401)
        
    db_session = DBSession()
    
    download_job = db_session.query(DownloadJob).filter(DownloadJob.id == id).first()
    if download_job is None:
        abort(404)
        
    try: 
        # Download jobs that are in progress cannot be deleted.
        if download_job.status is None or download_job.status == JobStatus.FAILED:
            db_session.delete(download_job)            
            db_session.commit()
        
        return jsonify({'status': 'OK'})

    except:  
        logger.exception('delete_download_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@app.route('/hosts/delete_all_failed_downloads/', methods=['DELETE'])
@login_required
def delete_all_failed_downloads():
    if not can_delete_install(current_user):
        abort(401)
        
    return delete_all_downloads(status=JobStatus.FAILED)


@app.route('/hosts/delete_all_scheduled_downloads/', methods=['DELETE'])
@login_required
def delete_all_scheduled_downloads():
    if not can_delete_install(current_user):
        abort(401)
        
    return delete_all_downloads()


def delete_all_downloads(status=None):        
    db_session = DBSession()
    
    try:
        download_jobs = db_session.query(DownloadJob).filter(DownloadJob.status == status)    
        for download_job in download_jobs:
            db_session.delete(download_job)
        
        db_session.commit()    

        return jsonify({'status': 'OK'})
    except:
        logger.exception('delete_download_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@app.route('/api/get_server_time')
@login_required
def api_get_server_time():  
    dict = {}
    db_session = DBSession()
    system = db_session.query(System).first()
    start_time = system.start_time

    dict['server_time'] = datetime.datetime.utcnow()
    dict['uptime'] = time_difference_UTC(start_time).strip(' ago')

    return jsonify(**{'data': dict})


@app.route('/api/get_hostnames/')
@login_required
def api_get_hostnames():
    """
    This method is called by ajax attached to Select2 (Search a host).
    The returned JSON contains the predefined tags.
    """
    db_session = DBSession()
    
    rows = []   
    criteria='%'
    if len(request.args) > 0:
        criteria += request.args.get('q') + '%'
 
    hosts = db_session.query(Host).filter(Host.hostname.like(criteria)).order_by(Host.hostname.asc()).all()   
    if len(hosts) > 0:
        for host in hosts:
            row = {}
            row['id'] = host.hostname
            row['text'] = host.hostname
            rows.append(row)
  
    return jsonify(**{'data': rows})


@app.route('/api/get_regions/')
@login_required
def api_get_regions():
    """
    This method is called by ajax attached to Select2 (Search a host).
    The returned JSON contains the predefined tags.
    """
    db_session = DBSession()
    
    rows = []   
    criteria = '%'
    if len(request.args) > 0:
        criteria += request.args.get('q') + '%'
 
    regions = db_session.query(Region).filter(Region.name.like(criteria)).order_by(Region.name.asc()).all()   
    if len(regions) > 0:
        rows.append({'id': 0, 'text': 'ALL'})
        for region in regions:
            rows.append({'id': region.id, 'text': region.name})
  
    return jsonify(**{'data': rows})


def get_install_scheduled_time_list():
    """
    Returns a list of unique Scheduled Time (in UTC) from the Job History.
    """
    result_list = []
    db_session = DBSession()
    
    scheduled_times = db_session.query(InstallJobHistory.scheduled_time).order_by(
                                       InstallJobHistory.scheduled_time.desc()).distinct()
    if scheduled_times is not None:
        for scheduled_time in scheduled_times:
            scheduled_time_string = get_datetime_string(scheduled_time[0])
            if scheduled_time_string not in result_list:
                result_list.append(scheduled_time_string)
            
    return result_list

         
@app.route('/api/install_completed/')
@login_required
def api_get_install_completed():
    db_session = DBSession()

    record_limit = request.args.get('record_limit')

    if record_limit is None or record_limit.lower() == 'all':  
        install_jobs = db_session.query(InstallJobHistory).filter(InstallJobHistory.status == JobStatus.COMPLETED). \
            order_by(InstallJobHistory.status_time.desc())
    else:  
        install_jobs = db_session.query(InstallJobHistory).filter(InstallJobHistory.status == JobStatus.COMPLETED). \
            order_by(InstallJobHistory.status_time.desc()).limit(record_limit)
              
    return jsonify(**get_install_job_json_dict(install_jobs))


@app.route('/api/install_dashboard/cookie')
@login_required
def api_get_install_dashboard_cookie():
    db_session = DBSession()
    system_option = SystemOption.get(db_session)

    completed_install_job_count = db_session.query(InstallJobHistory).filter(
        InstallJobHistory.status == JobStatus.COMPLETED).count()
    
    return jsonify(**{'data': [
        {'last_completed_install_job_count': completed_install_job_count,
         'can_schedule': system_option.can_schedule,
         'can_install': system_option.can_install
         }]})
    

@app.route('/hosts/schedule_install/', methods=['GET', 'POST'])
@login_required
def schedule_install():
    """
    For batch scheduled installation.
    """
    if not can_install(current_user):
        abort(401)

    db_session = DBSession()
    form = ScheduleInstallForm(request.form)
    
    # Fills the selections
    fill_regions(form.region.choices)
    fill_dependencies(form.dependency.choices)
    
    return_url = get_return_url(request, 'home')
    
    if request.method == 'POST':  # and form.validate():
        """
        f = request.form
        for key in f.keys():
            for value in f.getlist(key):
               print(key,":",value)
        """

        # Retrieves from the multi-select box
        hostnames = request.form.getlist('host-selector')

        install_action = form.install_action.data

        if hostnames is not None:

            for hostname in hostnames:
                host = get_host(db_session, hostname)
                if host is not None:
                    db_session = DBSession()
                    scheduled_time = form.scheduled_time_UTC.data
                    software_packages = form.software_packages.data
                    server = form.hidden_server.data
                    server_directory = form.hidden_server_directory.data
                    pending_downloads = form.hidden_pending_downloads.data
       
                    # If only one install_action, accept the selected dependency if any
                    dependency = 0
                    if len(install_action) == 1:
                        # No dependency when it is 0 (a digit)
                        if not form.dependency.data.isdigit():
                            prerequisite_install_job = get_last_install_action(db_session,
                                                                               form.dependency.data, host.id)
                            if prerequisite_install_job is not None:
                                dependency = prerequisite_install_job.id
                        create_or_update_install_job(db_session=db_session, host_id=host.id,
                                                     install_action=install_action[0],
                                                     scheduled_time=scheduled_time, software_packages=software_packages,
                                                     server=server, server_directory=server_directory,
                                                     pending_downloads=pending_downloads, dependency=dependency)
                    else:
                        # The dependency on each install action is already indicated in the implicit ordering
                        # in the selector.  If the user selected Pre-Upgrade and Install Add, Install Add (successor)
                        # will have Pre-Upgrade (predecessor) as the dependency.
                        dependency = 0              
                        for one_install_action in install_action:
                            new_install_job = create_or_update_install_job(db_session=db_session, host_id=host.id,
                                                                           install_action=one_install_action,
                                                                           scheduled_time=scheduled_time,
                                                                           software_packages=software_packages,
                                                                           server=server,
                                                                           server_directory=server_directory,
                                                                           pending_downloads=pending_downloads,
                                                                           dependency=dependency)
                            dependency = new_install_job.id
                                                  
        return redirect(url_for(return_url))
    else:                
        # Initialize the hidden fields
        form.hidden_server.data = -1
        form.hidden_server_name.data = ''
        form.hidden_server_directory.data = '' 
        form.hidden_pending_downloads.data = ''
            
        return render_template('schedule_install.html', form=form, system_option=SystemOption.get(db_session),
                               server_time=datetime.datetime.utcnow(), return_url=return_url,
                               install_action=get_install_actions_dict())

                                                       
@app.route('/hosts/<hostname>/schedule_install/', methods=['GET', 'POST'])
@login_required
def host_schedule_install(hostname):
    if not can_install(current_user):
        abort(401)
        
    return handle_schedule_install_form(request=request, db_session=DBSession(), hostname=hostname)


@app.route('/hosts/<hostname>/schedule_install/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
def host_schedule_install_edit(hostname, id):
    if not can_edit_install(current_user):
        abort(401)
        
    db_session = DBSession()
   
    install_job = db_session.query(InstallJob).filter(InstallJob.id == id).first()
    if install_job is None:
        abort(404)
    
    return handle_schedule_install_form(request=request, db_session=db_session,
                                        hostname=hostname, install_job=install_job)


@app.route('/hosts/download_dashboard/', methods=['GET', 'POST'])
@login_required
def download_dashboard():
    if not can_install(current_user):
        abort(401)
        
    return render_template('host/download_dashboard.html')


@app.route('/api/create_download_jobs')
@login_required
def api_create_download_jobs():
    try:
        server_id = request.args.get("server_id")
        server_directory = request.args.get("server_directory")
        smu_list = request.args.get("smu_list").split()
        pending_downloads = request.args.get("pending_downloads").split()
    
        # Derives the platform and release using the first SMU name.
        if len(smu_list) > 0 and len(pending_downloads) > 0:
            platform = get_platform(smu_list[0])
            release = get_release(smu_list[0])

            create_download_jobs(DBSession(), platform, release, pending_downloads, server_id, server_directory)
    except:
        try:
            logger.exception('api_create_download_jobs() hit exception')
        except:
            import traceback
            print traceback.format_exc()

        return jsonify({'status': 'Failed'})
    finally:
        return jsonify({'status': 'OK'})



def handle_schedule_install_form(request, db_session, hostname, install_job=None):    
    host = get_host(db_session, hostname)
    if host is None:
        abort(404)

    return_url = get_return_url(request, 'host_dashboard')

    form = HostScheduleInstallForm(request.form)
    
    # Retrieves all the install jobs for this host.  This will allow
    # the user to select which install job this install job can depend on.
    install_jobs = db_session.query(InstallJob).filter(
        InstallJob.host_id == host.id).order_by(InstallJob.scheduled_time.asc()).all()

    region_servers = host.region.servers
    # Returns all server repositories if the region does not have any server repository designated.
    if is_empty(region_servers):
        region_servers = get_server_list(db_session)

    # Fills the selections
    fill_servers(form.server_dialog_server.choices, region_servers)
    fill_servers(form.cisco_dialog_server.choices, region_servers, False)
    fill_dependency_from_host_install_jobs(form.dependency.choices, install_jobs,
                                           (-1 if install_job is None else install_job.id))
    fill_custom_command_profiles(form.custom_command_profile.choices)
        
    if request.method == 'POST':
        if install_job is not None:
            # In Edit mode, the install_action UI on HostScheduleForm is disabled (not allow to change).
            # Thus, there will be no value returned by form.install_action.data.  So, re-use the existing ones.
            install_action = [ install_job.install_action ]
        else:
            install_action = form.install_action.data

        scheduled_time = form.scheduled_time_UTC.data
        software_packages = form.software_packages.data
        server = form.hidden_server.data
        server_directory = form.hidden_server_directory.data
        pending_downloads = form.hidden_pending_downloads.data
        custom_command_profile = (',').join([str(i) for i in form.custom_command_profile.data])
        
        # install_action is a list object which may contain multiple install actions.
        # If only one install_action, accept the selected dependency if any
        if len(install_action) == 1:
            dependency = int(form.dependency.data)        
            create_or_update_install_job(db_session=db_session, host_id=host.id, install_action=install_action[0],
                                         scheduled_time=scheduled_time, software_packages=software_packages, server=server,
                                         server_directory=server_directory, pending_downloads=pending_downloads,
                                         custom_command_profile=custom_command_profile, dependency=dependency,
                                         install_job=install_job)
        else:
            # The dependency on each install action is already indicated in the implicit ordering in the selector.
            # If the user selected Pre-Upgrade and Install Add, Install Add (successor) will 
            # have Pre-Upgrade (predecessor) as the dependency.
            dependency = 0              
            for one_install_action in install_action:
                new_install_job = create_or_update_install_job(db_session=db_session,
                                                               host_id=host.id,
                                                               install_action=one_install_action,
                                                               scheduled_time=scheduled_time,
                                                               software_packages=software_packages, server=server,
                                                               server_directory=server_directory,
                                                               pending_downloads=pending_downloads,
                                                               custom_command_profile=custom_command_profile,
                                                               dependency=dependency, install_job=install_job)
                dependency = new_install_job.id
                   
        return redirect(url_for(return_url, hostname=hostname))
    
    elif request.method == 'GET':
        # Initialize the hidden fields
        form.hidden_server.data = -1
        form.hidden_server_name.data = ''
        form.hidden_server_directory.data = '' 
        form.hidden_pending_downloads.data = ''
        form.hidden_edit.data = install_job is not None

        # In Edit mode
        if install_job is not None:   
            form.install_action.data = install_job.install_action

            if install_job.server_id is not None:
                form.hidden_server.data = install_job.server_id
                server = get_server_by_id(db_session, install_job.server_id)
                if server is not None:
                    form.hidden_server_name.data = server.hostname
                   
                form.hidden_server_directory.data = '' if install_job.server_directory is None else install_job.server_directory
                
            form.hidden_pending_downloads.data = '' if install_job.pending_downloads is None else install_job.pending_downloads

            # Form a line separated list for the textarea
            if install_job.packages is not None:

                form.software_packages.data = '\n'.join(install_job.packages.split(','))
                
            form.dependency.data = str(install_job.dependency)
        
            if install_job.scheduled_time is not None:

                form.scheduled_time_UTC.data = get_datetime_string(install_job.scheduled_time)
        
            if install_job.custom_command_profile_id:
                ids = [int(id) for id in install_job.custom_command_profile_id.split(',')]
                form.custom_command_profile.data = ids

    return render_template('host/schedule_install.html', form=form, system_option=SystemOption.get(db_session),
                           host=host, server_time=datetime.datetime.utcnow(), install_job=install_job,
                           return_url=return_url, install_action=get_install_actions_dict())


def get_host_schedule_install_form(request, host):
    return HostScheduleInstallForm(request.form)


@app.route('/admin_console/', methods=['GET','POST'])
@login_required
def admin_console():
    if current_user.privilege != UserPrivilege.ADMIN:
        abort(401)
     
    db_session = DBSession()   

    smtp_form = SMTPForm(request.form)
    admin_console_form = AdminConsoleForm(request.form)    
    
    smtp_server = get_smtp_server(db_session)
    system_option = SystemOption.get(db_session)
    
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
        
        system_option.inventory_hour = admin_console_form.inventory_hour.data 
        system_option.inventory_history_per_host = admin_console_form.inventory_history_per_host.data 
        system_option.download_history_per_user = admin_console_form.download_history_per_user.data
        system_option.install_history_per_host = admin_console_form.install_history_per_host.data
        system_option.total_system_logs = admin_console_form.total_system_logs.data
        system_option.enable_default_host_authentication = admin_console_form.enable_default_host_authentication.data
        system_option.default_host_authentication_choice = admin_console_form.default_host_authentication_choice.data
        system_option.enable_cco_lookup = admin_console_form.enable_cco_lookup.data
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
                               is_ldap_supported=is_ldap_supported())


@app.route('/hosts/<hostname>/host_dashboard/')
@login_required
def host_dashboard(hostname):
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is None:
        abort(404)        
    
    return render_template('host/host_dashboard.html', host=host, 
                           form=get_host_schedule_install_form(request, host),
                           package_states=[PackageState.ACTIVE_COMMITTED,
                                           PackageState.ACTIVE,
                                           PackageState.INACTIVE_COMMITTED, PackageState.INACTIVE])


@app.route('/hosts/delete_all_failed_installs/', methods=['DELETE'])
@login_required
def delete_all_failed_installs():
    if not can_delete_install(current_user):
        abort(401)
        
    return delete_all_installs(status=JobStatus.FAILED)


@app.route('/hosts/delete_all_scheduled_installs/', methods=['DELETE'])
@login_required
def delete_all_scheduled_installs():
    if not can_delete_install(current_user):
        abort(401)
        
    return delete_all_installs()

    
def delete_all_installs(status=None):        
    db_session = DBSession()
    
    try:
        install_jobs = db_session.query(InstallJob).filter(InstallJob.status == status)    
        for install_job in install_jobs:
            db_session.delete(install_job)
            if status == JobStatus.FAILED:
                delete_install_job_dependencies(db_session, install_job)
        
        db_session.commit()    

        return jsonify({'status': 'OK'})
    except:
        logger.exception('delete_install_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@app.route('/hosts/<hostname>/delete_all_failed_installs/', methods=['DELETE'])
@login_required
def delete_all_failed_installs_for_host(hostname):
    if not can_delete_install(current_user):
        abort(401)
        
    return delete_all_installs_for_host(hostname=hostname, status=JobStatus.FAILED)


@app.route('/hosts/<hostname>/delete_all_scheduled_installs/', methods=['DELETE'])
@login_required
def delete_all_scheduled_installs_for_host(hostname):
    if not can_delete_install(current_user):
        abort(401)
        
    return delete_all_installs_for_host(hostname)


def delete_all_installs_for_host(hostname, status=None):
    if not can_delete_install(current_user):
        abort(401)
        
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is None:
        abort(404)
        
    try: 
        install_jobs = db_session.query(InstallJob).filter(
            InstallJob.host_id == host.id, InstallJob.status == status).all()
        if not install_jobs:
            return jsonify(status="No record fits the delete criteria.")
        
        for install_job in install_jobs:
            db_session.delete(install_job)
            if status == JobStatus.FAILED:
                delete_install_job_dependencies(db_session, install_job)
            
        db_session.commit()
        return jsonify({'status': 'OK'})
    except:
        logger.exception('delete_install_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@app.route('/hosts/<int:id>/delete_install_job/', methods=['DELETE'])
@login_required
def delete_install_job(id):
    if not can_delete_install(current_user):
        abort(401)
        
    db_session = DBSession()
    
    install_job = db_session.query(InstallJob).filter(InstallJob.id == id).first()
    if install_job is None:
        abort(404)
        
    try:
        # Install jobs that are in progress cannot be deleted.
        if install_job.status is None or install_job.status == JobStatus.FAILED:
            db_session.delete(install_job)        
        delete_install_job_dependencies(db_session, install_job)
        
        db_session.commit()
        
        return jsonify({'status': 'OK'})

    except:  
        logger.exception('delete_install_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})
    

def delete_install_job_dependencies(db_session, install_job):
    dependencies = db_session.query(InstallJob).filter(InstallJob.dependency == install_job.id).all()
    for dependency in dependencies:
        if dependency.status is None:
            db_session.delete(dependency)
        delete_install_job_dependencies(db_session, dependency)


@app.route('/hosts/<hostname>/<table>/session_log/<int:id>/')
@login_required
def host_session_log(hostname, table, id):
    """
    This route is also used by mailer.py for email notification.
    """
    db_session = DBSession()
    
    record = None   
    if table == 'install_job':
        record = db_session.query(InstallJob).filter(InstallJob.id == id).first()
    elif table == 'install_job_history':
        record = db_session.query(InstallJobHistory).filter(InstallJobHistory.id == id).first()
    elif table == 'inventory_job_history':
        record = db_session.query(InventoryJobHistory).filter(InventoryJobHistory.id == id).first()
    
    if record is None:
        abort(404)
       
    file_path = request.args.get('file_path')
    log_file_path = get_log_directory() + file_path

    if not(os.path.isdir(log_file_path) or os.path.isfile(log_file_path)):
        abort(404)

    file_pairs = {}
    log_file_contents = ''

    file_suffix = '.diff.html'
    if os.path.isdir(log_file_path):
        # Returns all files under the requested directory
        log_file_list = get_file_list(log_file_path)
        diff_file_list = [filename for filename in log_file_list if file_suffix in filename]

        for filename in log_file_list:
            diff_file_path = ''
            if file_suffix not in filename:
                if filename + file_suffix in diff_file_list:
                    diff_file_path = os.path.join(file_path, filename + file_suffix)
                file_pairs[os.path.join(file_path, filename)] = diff_file_path

        file_pairs = collections.OrderedDict(sorted(file_pairs.items()))
    else:        
        with io.open(log_file_path, "rt", encoding='latin-1') as fo:
            log_file_contents = fo.read()

    return render_template('host/session_log.html', hostname=hostname, table=table,
                           record_id=id, file_pairs=file_pairs, log_file_contents=log_file_contents,
                           is_file=os.path.isfile(log_file_path))


@app.route('/api/get_session_log_file_diff')
@login_required
def api_get_session_log_file_diff():
    diff_file_path = request.args.get("diff_file_path")

    if is_empty(diff_file_path):
        return jsonify({'status': 'diff file is missing.'})

    file_diff_contents = ''
    with io.open(os.path.join(get_log_directory(), diff_file_path), "rt", encoding='latin-1') as fo:
        file_diff_contents = fo.read()

    data = [{'file_diff_contents': file_diff_contents}]

    return jsonify(**{'data': data})


@app.route('/api/get_session_logs')
@login_required
def api_get_session_logs():
    id = request.args.get("record_id")

    db_session = DBSession()
    install_job = db_session.query(InstallJobHistory).filter(InstallJobHistory.id == id).first()

    if install_job is None:
        abort(404)

    log_folder = install_job.session_log
    file_path = os.path.join(get_log_directory(), log_folder)

    if not os.path.isdir(file_path):
        abort(404)

    rows = []
    log_file_list = get_file_list(file_path)
    for file in log_file_list:
        row = {}
        row['filepath'] = os.path.join(file_path, file)
        row['filename'] = file
        rows.append(row)

    return jsonify(**{'data': rows})


@app.route('/hosts/<hostname>/<table>/trace/<int:id>/')
@login_required
def host_trace(hostname, table, id):
    db_session = DBSession()
    
    trace = None
    if table == 'inventory_job_history':
        inventory_job = db_session.query(InventoryJobHistory).filter(InventoryJobHistory.id == id).first() 
        trace = inventory_job.trace if inventory_job is not None else None
    elif table == 'install_job':       
        install_job = db_session.query(InstallJob).filter(InstallJob.id == id).first() 
        trace = install_job.trace if install_job is not None else None
    elif table == 'install_job_history':
        install_job = db_session.query(InstallJobHistory).filter(InstallJobHistory.id == id).first()
        trace = install_job.trace if install_job is not None else None
    elif table == 'download_job':
        download_job = db_session.query(DownloadJob).filter(DownloadJob.id == id).first()
        trace = download_job.trace if download_job is not None else None
           
    return render_template('host/trace.html', hostname=hostname, trace=trace)


@app.route('/logs/')
@login_required
def logs():
    return render_template('log.html')


@app.route('/api/get_system_logs/')
@login_required
def api_get_system_logs():
    db_session = DBSession()

    # Only shows the ERROR
    logs = db_session.query(Log).filter(Log.level == 'ERROR').order_by(Log.created_time.desc())

    rows = []
    for log in logs:
        row = {}
        row['id'] = log.id
        row['severity'] = log.level
        row['message'] = log.msg
        row['created_time'] = log.created_time
        rows.append(row)

    return jsonify(**{'data': rows})


@app.route('/api/logs/<int:log_id>/trace/')
@login_required
def api_get_log_trace(log_id):
    """
    Returns the log trace of a particular log record.
    """
    db_session = DBSession()
    
    log = db_session.query(Log).filter(Log.id == log_id).first()
    return jsonify(**{'data': [
        {'severity': log.level, 'message': log.msg, 'trace': log.trace, 'created_time': log.created_time}
    ]})


@app.route('/failed_software_inventory_list/')
@login_required
def failed_software_inventory_list():
    db_session = DBSession()
    
    inventory_jobs = db_session.query(InventoryJob).filter(InventoryJob.status == JobStatus.FAILED)
    
    return render_template('failed_software_inventory.html', inventory_jobs=inventory_jobs)


@app.route('/api/hosts/')
@login_required
def api_host_list():
    db_session = DBSession()
    
    hosts = get_host_list(db_session)
    return get_host_json(hosts, request)


@app.route('/api/hosts/<hostname>/')
@login_required
def api_host(hostname):
    db_session = DBSession()
    
    host = get_host(db_session, hostname)
    return get_host_json([host], request)
    

@app.route('/api/hosts/search')
@login_required
def api_host_search_list():
    """
    Allows /api/hosts/search?hostname=%XX% type query
    """
    db_session = DBSession()
    
    criteria = '%'
    if len(request.args) > 0:
        criteria = request.args.get('hostname', '')
 
    hosts = db_session.query(Host).filter(Host.hostname.like(criteria)).order_by(Host.hostname.asc()).all()
    return get_host_json(hosts, request)


@app.route('/api/get_server_file_dict/<int:server_id>')
@login_required
def api_get_server_file_dict(server_id):
    """
    Returns an array of files on the server repository.  The dictionary contains
    ['filename'] = file
    ['is_directory'] = True|False
    """
    result_list, reachable = get_server_file_dict(server_id, request.args.get("server_directory"))
    if reachable:
        return jsonify(**{'data': result_list})
    else:
        return jsonify({'status': 'Failed'})


def get_server_file_dict(server_id, server_directory):
    """
    Returns an array of dictionaries which contain the file and directory listing
    """
    db_session = DBSession()
    server_file_dict = []
    reachable = False
    
    server = db_session.query(Server).filter(Server.id == server_id).first()
    if server is not None:
        server_impl = get_server_impl(server)
        if server_impl is not None:
            server_file_dict, reachable = server_impl.get_file_and_directory_dict(server_directory)

    return server_file_dict, reachable
    
    
@app.route('/api/get_last_successful_install_add_packages/hosts/<int:host_id>')
@login_required
def api_get_last_successful_install_add_packages(host_id):
    result_list = []
    db_session = DBSession()

    install_job_packages = db_session.query(InstallJobHistory.packages). \
        filter((InstallJobHistory.host_id == host_id), 
        and_(InstallJobHistory.install_action == InstallAction.INSTALL_ADD,
             InstallJobHistory.status == JobStatus.COMPLETED)). \
        order_by(InstallJobHistory.status_time.desc()).first()

    if install_job_packages is not None:
        result_list.append(install_job_packages)
    
    return jsonify(**{'data': result_list})


@app.route('/api/get_install_history/hosts/<hostname>')
@login_required
def api_get_install_history(hostname):    
    if not can_retrieve_software(current_user):
        abort(401)
    
    rows = []
    db_session = DBSession()
    
    host = get_host(db_session, hostname)
    if host is not None:
        install_jobs = db_session.query(InstallJobHistory). \
            filter((InstallJobHistory.host_id == host.id), 
            and_(InstallJobHistory.install_action == InstallAction.INSTALL_ADD,
                 InstallJobHistory.status == JobStatus.COMPLETED)). \
            order_by(InstallJobHistory.status_time.desc())
        
        for install_job in install_jobs:
            if not is_empty(install_job.packages):
                row = {}
                row['packages'] = install_job.packages
                row['status_time'] = install_job.status_time
                row['created_by'] = install_job.created_by
                rows.append(row)
    
    return jsonify(**{'data': rows})


@app.route('/api/get_servers')
@login_required
def api_get_servers():
    result_list = []
    db_session = DBSession()

    servers = get_server_list(db_session)
    if servers is not None:
        for server in servers:
            result_list.append({'server_id': server.id, 'hostname': server.hostname})
    
    return jsonify(**{'data': result_list})


@app.route('/api/get_servers/host/<hostname>')
@login_required
def api_get_servers_by_hostname(hostname):
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is not None:
        return api_get_servers_by_region(host.region_id)

    return jsonify(**{'data': []})


@app.route('/api/get_servers/region/<int:region_id>')
@login_required
def api_get_servers_by_region(region_id):
    result_list = [] 
    db_session = DBSession()

    region = get_region_by_id(db_session, region_id)
    if region is not None and len(region.servers) > 0:
        for server in region.servers:
            result_list.append({'server_id': server.id, 'hostname': server.hostname })
    else:
        # Returns all server repositories if the region does not have any server repository designated.
        return api_get_servers()

    return jsonify(**{'data': result_list})


@app.route('/api/get_nonlocal_servers/region/<int:region_id>')
@login_required
def api_get_nonlocal_servers_by_region(region_id):
    result_list = []
    db_session = DBSession()

    region = get_region_by_id(db_session, region_id)
    if region is not None and len(region.servers) > 0:
        for server in region.servers:
            if server.server_type != ServerType.LOCAL_SERVER:
                result_list.append({ 'server_id': server.id, 'hostname': server.hostname })
    else:
        servers = get_server_list(db_session)
        if servers is not None:
            for server in servers:
                if server.server_type != ServerType.LOCAL_SERVER:
                    result_list.append({'server_id': server.id, 'hostname': server.hostname})

    return jsonify(**{'data': result_list})


@app.route('/api/get_distinct_host_platforms')
@login_required
def api_get_distinct_host_platforms():
    rows = []
    db_session = DBSession()

    platforms = db_session.query(Host.software_platform).order_by(Host.software_platform.asc()).distinct()
    for platform in platforms:
        if platform[0] is not None:
            rows.append({'platform': platform[0]})

    return jsonify(**{'data': rows})


@app.route('/api/get_distinct_host_software_versions/platform/<platform>')
@login_required
def api_get_distinct_host_software_versions(platform):
    db_session = DBSession()

    software_versions = db_session.query(Host.software_version).filter(Host.software_platform == platform).\
        order_by(Host.software_version.asc()).distinct()

    rows = []
    for software_version in software_versions:
        if software_version[0] is not None:
            rows.append({'software_version': software_version[0]})

    return jsonify(**{'data': rows})


@app.route('/api/get_distinct_host_regions/platform/<platform>/software_versions/<software_versions>')
@login_required
def api_get_distinct_host_regions(platform, software_versions):
    """
    software_versions may equal to 'ALL' or multiple software versions
    """
    clauses = []
    db_session = DBSession()

    clauses.append(Host.software_platform == platform)
    if 'ALL' not in software_versions:
        clauses.append(Host.software_version.in_(software_versions.split(',')))

    region_ids = db_session.query(Host.region_id).filter(and_(*clauses)).distinct()

    # Change a list of tuples to a list
    region_ids_list = [region_id[0] for region_id in region_ids]

    rows = []
    if not is_empty(region_ids):
        regions = db_session.query(Region).filter(Region.id.in_(region_ids_list)). \
            order_by(Region.name.asc()).all()

        for region in regions:
            rows.append({'region_id': region.id, 'region_name': region.name})

    return jsonify(**{'data': rows})


@app.route('/api/get_distinct_host_roles/platform/<platform>/software_versions/<software_versions>/region_ids/<region_ids>')
@login_required
def api_get_distinct_host_roles(platform, software_versions, region_ids):
    """
    software_versions may equal to 'ALL' or multiple software versions
    region_ids may equal to 'ALL' or multiple region ids
    """
    clauses = []
    db_session = DBSession()

    clauses.append(Host.software_platform == platform)
    if 'ALL' not in software_versions:
        clauses.append(Host.software_version.in_(software_versions.split(',')))
    if 'ALL' not in region_ids:
        clauses.append(Host.region_id.in_(region_ids.split(',')))

    host_roles = db_session.query(Host.roles).filter(and_(*clauses)).distinct()

    # Change a list of tuples to a list
    # Example of roles_list  = [u'PE Router', u'PE1,R0', u'PE1,PE4', u'PE2,R1', u'Core']
    roles_list = [roles[0] for roles in host_roles if not is_empty(roles[0])]

    # Collapses the comma delimited strings to list
    roles_list = [] if is_empty(roles_list) else ",".join(roles_list).split(',')

    # Make the list unique, then sort it
    roles_list = sorted(list(set(roles_list)))

    rows = []
    for role in roles_list:
        rows.append({'role': role})

    return jsonify(**{'data': rows})


@app.route('/api/get_hosts/platform/<platform>/software_versions/<software_versions>/region_ids/<region_ids>/roles/<roles>')
@login_required
def api_get_hosts_by_platform(platform, software_versions, region_ids, roles):
    clauses = []
    db_session = DBSession()

    clauses.append(Host.software_platform == platform)
    if 'ALL' not in software_versions:
        clauses.append(Host.software_version.in_(software_versions.split(',')))

    if 'ALL' not in region_ids:
        clauses.append(Host.region_id.in_(region_ids.split(',')))

    # Retrieve relevant hosts
    hosts = db_session.query(Host).filter(and_(*clauses)).all()

    roles_list = [] if 'ALL' in roles else roles.split(',')

    rows = []
    for host in hosts:
        # Match on selected roles given by the user
        if not is_empty(roles_list):
            if not is_empty(host.roles):
                for role in host.roles.split(','):
                    if role in roles_list:
                        rows.append({'hostname': host.hostname})
                        break
        else:
            rows.append({'hostname': host.hostname})

    return jsonify(**{'data': rows})


@app.route('/api/get_hosts/region/<int:region_id>/role/<role>/software/<software>')
@login_required
def api_get_hosts_by_region(region_id, role, software):
    selected_roles = []
    selected_software = []

    if 'ALL' not in role:
        selected_roles = role.split(',')

    if 'ALL' not in software:
        selected_software = software.split(',')

    rows = []
    db_session = DBSession()    

    hosts = db_session.query(Host).filter(Host.region_id == region_id). \
        order_by(Host.hostname.asc())

    for host in hosts:
        host_roles = [] if host.roles is None else host.roles.split(',')
        if not selected_roles or any(role in host_roles for role in selected_roles):
            if host.software_platform is not None and host.software_version is not None:
                host_platform_software = host.software_platform + ' (' + host.software_version + ')'
            else:
                host_platform_software = 'Unknown'

            if not selected_software or host_platform_software in selected_software:
                row = {'hostname': host.hostname,
                       'roles': host.roles,
                       'platform_software': host_platform_software}

                rows.append(row)
    
    return jsonify(**{'data': rows})


@app.route('/api/get_software/<hostname>')
@login_required
def get_software(hostname):
    if not can_retrieve_software(current_user):
        abort(401)
    
    db_session = DBSession()
    
    host = get_host(db_session, hostname)
    if host is not None:
        if not host.inventory_job[0].request_update:
            host.inventory_job[0].request_update = True
            db_session.commit()
            return jsonify({'status': 'OK'})
   
    return jsonify({'status': 'Failed'})


@app.route('/api/hosts/<hostname>/password', methods=['DELETE'])
def api_remove_host_password(hostname):
    return remove_host_password(hostname)


@app.route('/api/hosts/<hostname>/enable_password', methods=['DELETE'])
def api_remove_host_enable_password(hostname):
    return remove_host_password(hostname, remove_enable_password=True)


def remove_host_password(hostname, remove_enable_password=False):
    if not can_create(current_user):
        abort(401)

    db_session = DBSession()
    host = get_host(db_session, hostname)
    if host is not None:
        if remove_enable_password:
            host.connection_param[0].enable_password = ''
        else:
            host.connection_param[0].password = ''
        db_session.commit()
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


@app.route('/api/jump_hosts/<hostname>/password', methods=['DELETE'])
@login_required   
def api_remove_jump_host_password(hostname):
    if not can_create(current_user):
        abort(401)
    
    db_session = DBSession()
    host = get_jump_host(db_session, hostname)
    if host is not None:
        host.password = ''
        db_session.commit()
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


@app.route('/api/check_host_reachability')
@login_required
def check_host_reachability():
    if not can_check_reachability(current_user):
        abort(401)
        
    urls = []   
    # Below information is directly from the page and 
    # may not have been saved yet.
    hostname = request.args.get('hostname')
    platform = request.args.get('platform')
    host_or_ip = request.args.get('host_or_ip')
    username = request.args.get('username')
    password = request.args.get('password')
    enable_password = request.args.get('enable_password')
    connection_type = request.args.get('connection_type')
    port_number = request.args.get('port_number')
    jump_host_id = request.args.get('jump_host')
    
    # If a jump host exists, create the connection URL
    if int(jump_host_id) > 0:
        db_session = DBSession()
        jump_host = get_jump_host_by_id(db_session=db_session, id=jump_host_id)
        if jump_host is not None:
            url = make_url(connection_type=jump_host.connection_type, host_username=jump_host.username,
                           host_password=jump_host.password, host_or_ip=jump_host.host_or_ip,
                           port_number=jump_host.port_number)
            urls.append(url)

    db_session = DBSession()
    # The form is in the edit mode and the user clicks Validate Reachability
    # If there is no password specified, get it from the database.
    if is_empty(password) or is_empty(enable_password):
        host = get_host(db_session, hostname)
        if host is not None:
            password = host.connection_param[0].password
            enable_password = host.connection_param[0].enable_password

    system_option = SystemOption.get(db_session)
    if system_option.enable_default_host_authentication:
        if not is_empty(system_option.default_host_username) and not is_empty(system_option.default_host_password):
            if system_option.default_host_authentication_choice == DefaultHostAuthenticationChoice.ALL_HOSTS or \
                (system_option.default_host_authentication_choice ==
                    DefaultHostAuthenticationChoice.HOSTS_WITH_NO_SPECIFIED_USERNAME_AND_PASSWORD and
                    is_empty(username) and is_empty(password)):
                username = system_option.default_host_username
                password = system_option.default_host_password
                
    url = make_url(
        connection_type=connection_type,
        host_username=username,
        host_password=password,
        host_or_ip=host_or_ip, 
        port_number=port_number,
        enable_password=enable_password)
    urls.append(url)
    
    return jsonify({'status': 'OK'}) if is_connection_valid(hostname, urls) else jsonify({'status': 'Failed'})


@app.route('/api/get_software_package_upgrade_list/hosts/<hostname>/release/<target_release>')
@login_required
def get_software_package_upgrade_list(hostname, target_release):
    rows = []
    db_session = DBSession()
    
    host = get_host(db_session, hostname)
    if host is None:
        abort(404)
    
    match_internal_name = True if request.args.get('match_internal_name') == 'true' else False
    host_packages = get_host_active_packages(hostname) 
    target_packages = get_target_software_package_list(host.family, host_packages, target_release, match_internal_name)
    for package in target_packages:
        rows.append({'package': package})
        
    return jsonify(**{'data': rows})


@app.route('/api/check_jump_host_reachability')
@login_required
def check_jump_host_reachability():
    if not can_check_reachability(current_user):
        abort(401)
       
    host_or_ip = request.args.get('host_or_ip')   
    connection_type = request.args.get('connection_type')
    port_number = request.args.get('port_number')
    
    port = 23  # default telnet port
    if len(port_number) > 0:
        port = int(port_number)
    elif connection_type == ConnectionType.SSH:
        port = 22
    
    return jsonify({'status': 'OK'}) if is_reachable(host_or_ip, port) else jsonify({'status': 'Failed'})


@app.route('/api/check_server_reachability')
@login_required
def check_server_reachability():
    if not can_check_reachability(current_user):
        abort(401)
            
    hostname = request.args.get('hostname')
    server_type = request.args.get('server_type')
    server_url = request.args.get('server_url')
    username = request.args.get('username')
    password = request.args.get('password')
    server_directory = request.args.get('server_directory')
    
    server = Server(hostname=hostname, server_type=server_type, server_url=server_url, 
                    username=username, password=password, server_directory=server_directory)
    # The form is in the edit mode and the user clicks Validate Reachability
    # If there is no password specified, try get it from the database.
    if (server_type == ServerType.FTP_SERVER or server_type == ServerType.SFTP_SERVER) and password == '':
        db_session = DBSession()
        server_in_db = get_server(db_session, hostname)
        if server_in_db is not None:
            server.password = server_in_db.password

    server_impl = get_server_impl(server)
    return jsonify({'status': 'OK'}) if server_impl.check_reachability() else jsonify({'status': 'Failed'})


@app.route('/api/validate_cisco_user', methods=['POST'])
@login_required
def validate_cisco_user():   
    if not can_check_reachability(current_user):
        abort(401)
    
    try:
        username = request.form['username']      
        password = request.form['password']
    
        if len(password) == 0:
            password = Preferences.get(DBSession(), current_user.id).cco_password
    
        BSDServiceHandler.get_access_token(username, password)
        return jsonify({'status': 'OK'})
    except KeyError:
        return jsonify({'status': 'Failed'})
    except:
        logger.exception('validate_cisco_user() hit exception')
        return jsonify({'status': 'Failed'})


def get_host_json(hosts, request):    
    if hosts is None:
        response = jsonify({'status': 'Not Found'})
        response.status = 404
        return response
        
    hosts_list = []       
    for host in hosts:
        hosts_list.append(host.get_json())
    
    return jsonify(**{'host': hosts_list})


def get_install_actions_dict():
    return {
        "pre_upgrade": InstallAction.PRE_UPGRADE, 
        "add": InstallAction.INSTALL_ADD,
        "activate": InstallAction.INSTALL_ACTIVATE,
        "post_upgrade": InstallAction.POST_UPGRADE,
        "commit": InstallAction.INSTALL_COMMIT,
        "remove": InstallAction.INSTALL_REMOVE,
        "deactivate": InstallAction.INSTALL_DEACTIVATE,
        "rollback": InstallAction.INSTALL_ROLLBACK,
        "all": InstallAction.ALL,
    }



def get_return_url(request, default_url=None):
    """
    Returns the return_url encoded in the parameters
    """
    url = request.args.get('return_url')
    if url is None:
        url = default_url
    return url


@app.errorhandler(401)
def error_not_authorized(error):
    return render_template('user/not_authorized.html', user=current_user)


@app.errorhandler(404)
def error_not_found(error):
    return render_template('error/not_found.html'), 404   


@app.errorhandler(500)
def catch_server_errors(e):
    logger.exception("Server error!")   


@app.route('/shutdown')
def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    
    return 'Flask has been shutdown'


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session = DBSession()
    db_session.close()


# Setup logging for production.
if not app.debug:
    app.logger.addHandler(logging.StreamHandler()) # Log to stderr.
    app.logger.setLevel(logging.INFO)


def event_stream():
    return 'data: testing\n\n'


@app.route('/stream')
def stream():
    return Response(event_stream(),
                    mimetype="text/event-stream")


@app.route('/about')
@login_required
def about():    
    return render_template('about.html', build_date=get_build_date())


def get_build_date(): 
    try:
        return open('build_date', 'r').read()
    except:
        pass
    
    return None


@app.route('/user_preferences', methods=['GET','POST'])
@login_required
def user_preferences(): 
    db_session = DBSession()
    form = PreferencesForm(request.form)
 
    user = get_user_by_id(db_session, current_user.id)
     
    if request.method == 'POST' and form.validate():
        user.preferences[0].cco_username = form.cco_username.data 
        
        if len(form.cco_password.data) > 0:
            user.preferences[0].cco_password = form.cco_password.data 
        
        # All the checked checkboxes (i.e. platforms and releases to exclude).
        values = request.form.getlist('check') 
        excluded_platform_list = ','.join(values)
        
        preferences = Preferences.get(db_session, current_user.id)
        preferences.excluded_platforms_and_releases = excluded_platform_list
            
        db_session.commit()
        
        return redirect(url_for('home'))
    else:
        preferences = user.preferences[0]
        form.cco_username.data = preferences.cco_username

        if not is_empty(user.preferences[0].cco_password):
            form.password_placeholder = 'Use Password on File'
        else:
            form.password_placeholder = 'No Password Specified'

    return render_template('csm_client/preferences.html', form=form,
                           platforms_and_releases=get_platforms_and_releases_dict(db_session))


def get_platforms_and_releases_dict(db_session):
    excluded_platform_list = []
    preferences = Preferences.get(db_session, current_user.id)
    
    # It is possible that the preferences have not been created yet.
    if preferences is not None and preferences.excluded_platforms_and_releases is not None:
        excluded_platform_list = preferences.excluded_platforms_and_releases.split(',')
    
    rows = []    
    catalog = SMUInfoLoader.get_catalog()
    if len(catalog) > 0:
        for platform in catalog:
            releases = catalog[platform]
            for release in releases:
                row = {}
                row['platform'] = platform
                row['release'] = release
                row['excluded'] = True if platform + '_' + release in excluded_platform_list else False
                rows.append(row)
    else:
        # If get_catalog() failed, populate the excluded platforms and releases
        for platform_and_release in excluded_platform_list:
            pos = platform_and_release.rfind('_')
            if pos > 0:
                row = {}
                row['platform'] = platform_and_release[:pos]
                row['release'] = platform_and_release[pos+1:]
                row['excluded'] = True
                rows.append(row)
            
    return rows


@app.route('/get_smu_list/platform/<platform>/release/<release>')
@login_required
def get_smu_list(platform, release):        
    system_option = SystemOption.get(DBSession())
    form = BrowseServerDialogForm(request.form)
    fill_servers(form.dialog_server.choices, get_server_list(DBSession()), False)
    
    return render_template('csm_client/get_smu_list.html', form=form, platform=platform,
                           release=release, system_option=system_option)


@app.route('/api/get_smu_list/platform/<platform>/release/<release>')
@login_required
def api_get_smu_list(platform, release):    
    smu_loader = SMUInfoLoader(platform, release)
    if smu_loader.smu_meta is None:
        return jsonify(**{'data': []})

    hostname = request.args.get('hostname')
    hide_installed_packages = request.args.get('hide_installed_packages')

    if request.args.get('filter') == 'Optimal':
        return get_smu_or_sp_list(hostname, hide_installed_packages,
                                  smu_loader.get_optimal_smu_list(), smu_loader.file_suffix)
    else:
        return get_smu_or_sp_list(hostname, hide_installed_packages,
                                  smu_loader.get_smu_list(), smu_loader.file_suffix)


@app.route('/api/get_sp_list/platform/<platform>/release/<release>')
@login_required
def api_get_sp_list(platform, release):  
    smu_loader = SMUInfoLoader(platform, release)
    if smu_loader.smu_meta is None:
        return jsonify(**{'data': []})

    hostname = request.args.get('hostname')
    hide_installed_packages = request.args.get('hide_installed_packages')

    if request.args.get('filter') == 'Optimal':
        return get_smu_or_sp_list(hostname, hide_installed_packages,
                                  smu_loader.get_optimal_sp_list(), smu_loader.file_suffix)
    else:
        return get_smu_or_sp_list(hostname, hide_installed_packages,
                                  smu_loader.get_sp_list(), smu_loader.file_suffix)


@app.route('/api/get_tar_list/platform/<platform>/release/<release>')
@login_required
def api_get_tar_list(platform, release):
    smu_loader = SMUInfoLoader(platform, release)
    file_list = get_file_list(get_repository_directory(), '.tar')

    if smu_loader.smu_meta is None:
        return jsonify(**{'data': []})
    else:
        tars_list = smu_loader.get_tar_list()
        rows = []
        for tar_info in tars_list:
            row = {}
            row['ST'] = 'True' if tar_info.name in file_list else 'False'
            row['name'] = tar_info.name
            row['compressed_size'] = tar_info.compressed_image_size
            row['description'] = ""
            rows.append(row)

    return jsonify(**{'data': rows})


def get_smu_or_sp_list(hostname, hide_installed_packages, smu_info_list, file_suffix):
    """
    Return the SMU/SP list.  If hostname is given, compare its active packages.
    """
    file_list = get_file_list(get_repository_directory(), '.' + file_suffix)

    host_packages = [] if hostname is None else get_host_active_packages(hostname)
    
    rows = []  
    for smu_info in smu_info_list:

        # Verify if the package has already been installed.
        installed = False
        for host_package in host_packages:
            if smu_info.name in host_package:
                installed = True
                break

        include = False if (hide_installed_packages == 'true' and installed) else True
        if include:
            row = {}
            row['ST'] = 'True' if smu_info.name + '.' + file_suffix in file_list else 'False'
            row['package_name'] = smu_info.name + '.' + file_suffix
            row['posted_date'] = smu_info.posted_date.split()[0]
            row['ddts'] = smu_info.ddts
            row['ddts_url'] = BUG_SEARCH_URL + smu_info.ddts
            row['type'] = smu_info.type
            row['description'] = smu_info.description
            row['impact'] = smu_info.impact
            row['functional_areas'] = smu_info.functional_areas
            row['id'] = smu_info.id
            row['name'] = smu_info.name
            row['status'] = smu_info.status
            row['package_bundles'] = smu_info.package_bundles
            row['compressed_image_size'] = smu_info.compressed_image_size
            row['uncompressed_image_size'] = smu_info.uncompressed_image_size
            row['is_installed'] = installed

            if not is_empty(hostname) and SMU_INDICATOR in smu_info.name:
                row['is_applicable'] = is_smu_applicable(host_packages, smu_info.package_bundles)
            else:
                row['is_applicable'] = True

            rows.append(row)

    return jsonify(**{'data': rows})


def is_smu_applicable(host_packages, required_package_bundles):
    """
    Only SMU should go through this logic
    The package_bundles defined must be satisfied for the SMU to be applicable.
    However,asr9k-fpd-px can be excluded.
    """
    if not is_empty(required_package_bundles):
        package_bundles = required_package_bundles.split(',')
        package_bundles = [p for p in package_bundles if p != 'asr9k-fpd-px']

        count = 0
        for package_bundle in package_bundles:
            for host_package in host_packages:
                if package_bundle in host_package:
                    count += 1
                    break

        if count != len(package_bundles):
            return False

    return True


@app.route('/api/get_ddts_details/ddts_id/<ddts_id>')
@login_required
def api_get_ddts_details(ddts_id):
    username = Preferences.get(DBSession(), current_user.id).cco_username
    password = Preferences.get(DBSession(), current_user.id).cco_password
    bsh = BugServiceHandler(username, password, ddts_id)
    try:
        bug_info = bsh.get_bug_info()
    except Exception as e:
        logger.exception('api_get_ddts_details() hit exception ' + e.message)
        if e.message == 'access_token':
            error_msg = 'Could not retrieve bug information.  The username and password defined may not be correct ' \
                        '(Check Tools - User Preferences)'
        else:
            error_msg = 'Could not retrieve bug information.'
        return jsonify(**{'data': {'ErrorMsg': error_msg}})

    info = {}

    statuses = {'O': 'Open',
                'F': 'Fixed',
                'T': 'Terminated'}

    severities = {'1': "1 Catastrophic",
                  '2': "2 Severe",
                  '3': "3 Moderate",
                  '4': "4 Minor",
                  '5': "5 Cosmetic",
                  '6': "6 Enhancement"}

    info['status'] = statuses[get_json_value(bug_info, 'status')] \
        if get_json_value(bug_info, 'status') in statuses else get_json_value(bug_info, 'status')
    info['product'] = get_json_value(bug_info, 'product')
    info['severity'] = severities[get_json_value(bug_info, 'severity')] \
        if get_json_value(bug_info, 'severity') in severities else get_json_value(bug_info, 'severity')
    info['headline'] = get_json_value(bug_info, 'headline')
    info['support_case_count'] = get_json_value(bug_info, 'support_case_count')
    info['last_modified_date'] = get_json_value(bug_info, 'last_modified_date')
    info['bug_id'] = get_json_value(bug_info, 'bug_id')
    info['created_date'] = get_json_value(bug_info, 'created_date')
    info['duplicate_of'] = get_json_value(bug_info, 'duplicate_of')
    info['description'] = get_json_value(bug_info, 'description').replace('\n', '<br>') \
        if get_json_value(bug_info, 'description') else None
    info['known_affected_releases'] = get_json_value(bug_info, 'known_affected_releases').replace(' ', '<br>') \
        if get_json_value(bug_info, 'known_affected_releases') else None
    info['known_fixed_releases'] = get_json_value(bug_info, 'known_fixed_releases').replace(' ', '<br>') \
        if get_json_value(bug_info, 'known_fixed_releases') else None
    info['ErrorDescription'] = get_json_value(bug_info, 'ErrorDescription')
    info['SuggestedAction'] = get_json_value(bug_info, 'SuggestedAction')

    return jsonify(**{'data': info})


@app.route('/api/get_smu_details/smu_id/<smu_id>')
@login_required
def api_get_smu_details(smu_id):
    rows = []
    db_session = DBSession()
    
    smu_info = db_session.query(SMUInfo).filter(SMUInfo.id == smu_id).first()
    if smu_info is not None:
        row = {}
        row['id'] = smu_info.id
        row['name'] = smu_info.name
        row['status'] = smu_info.status
        row['type'] = smu_info.type
        row['posted_date'] = smu_info.posted_date
        row['ddts'] = smu_info.ddts
        row['description'] = smu_info.description
        row['functional_areas'] = smu_info.functional_areas
        row['impact'] = smu_info.impact
        row['package_bundles'] = smu_info.package_bundles
        row['compressed_image_size'] = str(smu_info.compressed_image_size)
        row['uncompressed_image_size'] = str(smu_info.uncompressed_image_size)
        row['prerequisites'] = smu_info.prerequisites
        row['supersedes'] = smu_info.supersedes
        row['superseded_by'] = smu_info.superseded_by
        row['composite_DDTS'] = smu_info.composite_DDTS
        row['prerequisites_smu_ids'] = get_smu_ids(db_session, smu_info.prerequisites)
        row['supersedes_smu_ids'] = get_smu_ids(db_session, smu_info.supersedes)
        row['superseded_by_smu_ids'] = get_smu_ids(db_session, smu_info.superseded_by)

        rows.append(row)

    return jsonify(**{'data': rows})


def get_smu_ids(db_session, smu_name_list):
    smu_ids = []
    smu_names = comma_delimited_str_to_list(smu_name_list)
    for smu_name in smu_names:
        smu_info = db_session.query(SMUInfo).filter(SMUInfo.name == smu_name).first()
        if smu_info is not None:
            smu_ids.append(smu_info.id)
        else:
            smu_ids.append('Unknown')
                  
    return ','.join([id for id in smu_ids])

    
@app.route('/api/get_smu_meta_retrieval_elapsed_time/platform/<platform>/release/<release>')
@login_required
def api_get_smu_meta_retrieval_elapsed_time(platform, release):
    smu_meta = DBSession().query(SMUMeta).filter(SMUMeta.platform_release == platform + '_' + release).first()
    
    retrieval_elapsed_time = 'Unknown'
    if smu_meta is not None:
        retrieval_elapsed_time = time_difference_UTC(smu_meta.retrieval_time)

    return jsonify(**{'data': [{'retrieval_elapsed_time': retrieval_elapsed_time}]})
    
    
@app.route('/validate_software')
@login_required
def validate_software():
    server_dialog_form = ServerDialogForm(request.form)
    software_profile_form = SoftwareProfileForm(request.form)

    return render_template('csm_client/validate_software.html',
                           server_dialog_form=server_dialog_form,
                           software_profile_form=software_profile_form,
                           system_option=SystemOption.get(DBSession()))


@app.route('/api/check_cisco_authentication/', methods=['POST'])
@login_required
def check_cisco_authentication():
    preferences = Preferences.get(DBSession(), current_user.id) 
    if preferences is not None:
        if not is_empty(preferences.cco_username) and not is_empty(preferences.cco_password):
            return jsonify({'status': 'OK'})
    
    return jsonify({'status': 'Failed'})


@app.route('/api/get_catalog')
@login_required
def api_get_catalog():  
    db_session = DBSession()
    excluded_platform_list = []
    
    preferences = Preferences.get(db_session, current_user.id)  
    if preferences.excluded_platforms_and_releases is not None:
        excluded_platform_list = preferences.excluded_platforms_and_releases.split(',')
        
    rows = []
    
    catalog = SMUInfoLoader.get_catalog()
    for platform in catalog:
        releases = get_filtered_platform_list(platform, catalog[platform], excluded_platform_list)
        if len(releases) > 0:
            row = {}
            row['platform'] = platform
            row['beautified_platform'] = beautify_platform(platform)
            row['releases'] = releases
            rows.append(row)
    
    return jsonify(**{'data': rows})


def get_filtered_platform_list(platform, releases, excluded_platform_list):
    result_list = []
    for release in releases:
        if platform + '_' + release not in excluded_platform_list:
            result_list.append(release)
            
    return result_list


@app.route('/api/get_missing_files_on_server/<int:server_id>')
@login_required
def api_get_missing_files_on_server(server_id):
    """
    Given a SMU list, return the ones that are missing in the server repository.
    """
    rows = []    
    smu_list = request.args.get('smu_list').split()
    server_directory = request.args.get('server_directory')

    server_file_dict, is_reachable = get_server_file_dict(server_id, server_directory)

    # Identify if the SMUs are downloadable on CCO or not. 
    # If they are engineering SMUs, they cannot be downloaded.
    download_info_dict, smu_loader = get_download_info_dict(smu_list)

    if is_reachable:
        for smu_name, cco_filename in download_info_dict.items():
            if not is_smu_on_server_repository(server_file_dict, smu_name):
                smu_info = smu_loader.get_smu_info(smu_name.replace('.' + smu_loader.file_suffix, ''))
                description = '' if smu_info is None else smu_info.description
                # If selected SMU on CCO
                if cco_filename is not None:             
                    rows.append({'smu_entry': smu_name, 'description': description,
                                 'cco_filename': cco_filename, 'is_downloadable': True})
                else:
                    rows.append({'smu_entry': smu_name, 'description': description,
                                 'is_downloadable': False})
    else:
        return jsonify({'status': 'Failed'})

    return jsonify(**{'data': rows})


@app.route('/api/check_is_tar_downloadable')
def check_is_tar_downloadable():
    rows = []
    smu_list = request.args.get('smu_list').split()

    # Identify if the SMUs are downloadable on CCO or not.
    # If they are engineering SMUs, they cannot be downloaded.
    download_info_dict, smu_loader = get_download_info_dict(smu_list)

    for smu_name, cco_filename in download_info_dict.items():
        smu_info = smu_loader.get_smu_info(smu_name.replace('.' + smu_loader.file_suffix, ''))
        description = '' if smu_info is None else smu_info.description
        # If selected TAR on CCO
        if cco_filename is not None:
            rows.append({'smu_entry': smu_name, 'description': description,
                         'cco_filename': cco_filename, 'is_downloadable': True})
        else:
            rows.append({'smu_entry': smu_name, 'description': description,
                         'is_downloadable': False})

    return jsonify(**{'data': rows})


def is_smu_on_server_repository(server_file_dict, smu_name):
    for file_info in server_file_dict:
        if not file_info['is_directory'] and file_info['filename'] == smu_name:
            return True
    return False


@app.route('/api/refresh_all_smu_info')
@login_required
def api_refresh_all_smu_info():  
    if SMUInfoLoader.refresh_all():
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


@app.route('/api/get_cco_lookup_time')
@login_required
def api_get_cco_lookup_time():  
    system_option = SystemOption.get(DBSession())
    if system_option.cco_lookup_time is not None:
        return jsonify(**{'data': [{'cco_lookup_time': get_datetime_string(system_option.cco_lookup_time)}]})
    else:
        return jsonify({'status': 'Failed'})
    

@app.route('/api/get_missing_prerequisite_list')
@login_required
def api_get_missing_prerequisite_list():
    """
    Given a SMU list, return any missing pre-requisites.  The
    SMU entries returned also have the file extension appended.
    """
    hostname = request.args.get('hostname')
    # The SMUs selected by the user to install
    smu_list = request.args.get('smu_list').split()

    rows = []
    platform, release = get_platform_and_release(smu_list)
    if platform != UNKNOWN and release != UNKNOWN:
        smu_loader = SMUInfoLoader(platform, release)

        prerequisite_list = get_missing_prerequisite_list(smu_list)
        host_packages = get_host_active_packages(hostname)

        for smu_name in prerequisite_list:
            # If the missing pre-requisites have not been installed
            # (i.e. not in the Active/Active-Committed), include them.
            if not host_packages_contains(host_packages, smu_name):
                smu_info = smu_loader.get_smu_info(smu_name.replace('.' + smu_loader.file_suffix, ''))
                description = '' if smu_info is None else smu_info.description
                rows.append({'smu_entry': smu_name, 'description': description})

    return jsonify(**{'data': rows})


@app.route('/api/get_reload_list')
@login_required
def api_get_reload_list():
    """
    Given a software package/SMU/SP list, return those
    that require router reload.
    """
    # The software packages/SMUs/SPs selected by the user to install
    package_list = request.args.get('package_list').split()   
    
    rows = []    
    if not is_empty(package_list):
        # Identify the platform and release
        platform, release = get_platform_and_release(package_list)
        if platform != UNKNOWN and release != UNKNOWN:
            smu_loader = SMUInfoLoader(platform, release)
            if smu_loader.is_valid:
                for package_name in package_list:
                    if 'mini' in package_name:
                        rows.append({'entry': package_name, 'description': ''})
                    else:
                        # Strip the suffix
                        smu_info = smu_loader.get_smu_info(package_name.replace('.' + smu_loader.file_suffix, ''))
                        if smu_info is not None:
                            if "Reload" in smu_info.impact or "Reboot" in smu_info.impact:
                                rows.append({'entry': package_name, 'description': smu_info.description})

    return jsonify(**{'data': rows})


def host_packages_contains(host_packages, smu_name):
    for package in host_packages:
        # Performs a partial match
        if smu_name.replace('.pie', '') in package:
            return True
    return False


@app.route('/api/validate_software')
@login_required
def api_validate_software():
    smu_list = request.args.get('smu_list').split()
    return jsonify(**{'data': get_validated_list(smu_list)})


# This route will prompt a file download
@app.route('/download_session_log')
@login_required
def download_session_log():
    return send_file(get_log_directory() + request.args.get('file_path'), as_attachment=True)


@app.route('/api/download_session_logs', methods=['POST'])
@login_required
def api_download_session_logs():
    file_list = request.args.getlist('file_list[]')[0].split(',')
    temp_user_dir = create_temp_user_directory(current_user.username)
    session_zip_path = os.path.normpath(os.path.join(temp_user_dir, "session_logs"))
    zip_file = os.path.join(session_zip_path, "session_logs.zip")
    create_directory(session_zip_path)
    make_file_writable(session_zip_path)

    zout = zipfile.ZipFile(zip_file, mode='w')
    for f in file_list:
        zout.write(os.path.normpath(f), os.path.basename(f))

    zout.close()

    return send_file(zip_file, as_attachment=True)


@app.route('/download_system_logs')
@login_required
def download_system_logs():
    db_session = DBSession()
    logs = db_session.query(Log) \
        .order_by(Log.created_time.desc())
        
    contents = ''
    for log in logs:
        contents += get_datetime_string(datetime_from_utc_to_local(log.created_time)) + '\n'
        contents += log.level + ':' + log.msg + '\n'
        if log.trace is not None:
            contents += log.trace + '\n'
        contents += '-' * 70 + '\n'
        
    # Create a file which contains the size of the image file.
    temp_user_dir = create_temp_user_directory(current_user.username)
    log_file_path = os.path.normpath(os.path.join(temp_user_dir, "system_logs"))
    create_directory(log_file_path)
    make_file_writable(log_file_path)
    log_file = open(os.path.join(log_file_path, 'system_logs'), 'w')
    log_file.write(contents)
    log_file.close()

    return send_file(os.path.join(log_file_path, 'system_logs'), as_attachment=True)


@app.route('/api/plugins')
@login_required
def plugins():
    pm = PluginManager()
    pm.locate_plugins()
    plugins = pm.load_plugins()
    info = [plugin.to_dict() for plugin in plugins]
    return jsonify(**{"data": info})

@app.route('/api/plugins/<name>')
@login_required
def plugin_by_name(name):
    pm = PluginManager()
    pm.locate_plugins()
    pm.load_plugins()
    plugins = pm.get_plugins_by_name(name)
    if not isinstance(plugins, list):
        plugin = [plugins.to_dict()]
    else:
        plugin = [plugin.to_dict() for plugin in plugins]
    return jsonify(**{"data": plugin})


if __name__ == '__main__':
    initialize.init()  
    app.run(host='0.0.0.0', use_reloader=False, threaded=True, debug=False)






