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
from flask import jsonify
from flask import abort
from flask import send_file
from flask import request
from flask import Response
from flask import redirect
from flask import url_for
from flask.ext.login import LoginManager
from flask.ext.login import current_user
from flask.ext.login import login_required


from werkzeug.contrib.fixers import ProxyFix

from sqlalchemy import and_

from database import DBSession
from forms import ScheduleInstallForm
from forms import HostScheduleInstallForm

from models import Host
from models import Log, logger 
from models import InventoryJobHistory
from models import InstallJob
from models import InstallJobHistory
from models import Region
from models import User
from models import Server
from models import SystemOption
from models import Package
from models import DownloadJob
from models import CSMMessage
from models import Preferences

from constants import InstallAction
from constants import JobStatus
from constants import ServerType
from constants import UserPrivilege
from constants import UNKNOWN
from constants import get_log_directory
from constants import PlatformFamily

from common import get_host_active_packages 
from common import fill_servers
from common import fill_dependencies
from common import fill_dependency_from_host_install_jobs
from common import fill_regions
from common import fill_custom_command_profiles
from common import get_host
from common import get_host_list
from common import get_jump_host_list
from common import get_server_by_id
from common import get_server_list
from common import get_region
from common import get_region_by_id
from common import can_check_reachability
from common import can_retrieve_software
from common import can_install
from common import can_edit_install
from common import create_or_update_install_job
from common import get_last_install_action
from common import get_last_completed_install_job_for_install_action
from common import download_session_logs

from filters import get_datetime_string

from utils import get_file_list
from utils import is_empty
from utils import create_directory
from utils import create_temp_user_directory
from utils import make_file_writable
from utils import get_return_url
from utils import get_build_date

from server_helper import get_server_impl

from smu_utils import get_missing_prerequisite_list
from smu_utils import get_download_info_dict

from smu_info_loader import SMUInfoLoader
from cisco_service.bsd_service import BSDServiceHandler

from package_utils import get_target_software_package_list
from package_utils import strip_smu_file_extension
from restful import restful_api

from views.home import home
from views.cco import cco
from views.authenticate import authenticate
from views.asr9k_64_migrate import asr9k_64_migrate
from views.conformance import conformance
from views.inventory import inventory, update_select2_options
from views.tar_support import tar_support
from views.host_import import host_import
from views.custom_command import custom_command
from views.datatable import datatable
from views.host_dashboard import host_dashboard
from views.install_dashboard import install_dashboard
from views.download_dashboard import download_dashboard
from views.admin_console import admin_console

import os
import io
import logging
import datetime
import filters
import collections
import initialize

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

app.register_blueprint(home)
app.register_blueprint(authenticate)
app.register_blueprint(restful_api)
app.register_blueprint(asr9k_64_migrate)
app.register_blueprint(conformance)
app.register_blueprint(inventory)
app.register_blueprint(tar_support)
app.register_blueprint(host_import)
app.register_blueprint(custom_command)
app.register_blueprint(datatable)
app.register_blueprint(host_dashboard)
app.register_blueprint(install_dashboard)
app.register_blueprint(download_dashboard)
app.register_blueprint(admin_console)
app.register_blueprint(cco)

# Hook up the filters
filters.init(app)

app.secret_key = 'CSMSERVER'
    
# Use Flask-Login to track the current user in Flask's session.
login_manager = LoginManager()
login_manager.setup_app(app)
login_manager.login_view = 'authenticate.login'
login_manager.login_message = 'Please log in.'


@login_manager.user_loader
def load_user(user_id):
    """Hook for Flask-Login to load a User instance from a user ID."""
    db_session = DBSession()
    return db_session.query(User).get(user_id)


@app.route('/')
@login_required
def home():
    return redirect(url_for('home.dashboard'))


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
    return render_template('host/index.html')


@app.route('/jump_hosts/')
@login_required
def jump_host_list():
    db_session = DBSession()
  
    hosts = get_jump_host_list(db_session)
    if hosts is None:
        abort(404)
            
    return render_template('jump_host/index.html', hosts=hosts)


@app.route('/api/hosts/<hostname>/packages')
@login_required
def api_get_host_packages_by_states(hostname):
    """
    Returns the software packages that satisfy the requested package states (e.g. 'active,committed')
    """
    package_state = request.args.get('package_state')
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

        for package in packages:
            rows.append({'package': package.name if package.location is None else package.location + ':' + package.name})

    return jsonify(**{'data': rows})


@app.route('/api/get_hostnames/')
@login_required
def api_get_hostnames():
    """
    This method is called by ajax attached to Select2 (Search a host).
    The returned JSON contains the predefined tags.
    """
    return update_select2_options(request.args, Host.hostname)


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
    fill_custom_command_profiles(form.custom_command_profile.choices)
    
    return_url = get_return_url(request, 'home')
    
    if request.method == 'POST':  # and form.validate():
        """
        f = request.form
        for key in f.keys():
            for value in f.getlist(key):
               print(key,":",value)
        """
        # Retrieves from the multi-select box
        hostnames = form.hidden_selected_hosts.data.split(',')
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
                               server_time=datetime.datetime.utcnow(), return_url=return_url)

                                                       
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


@app.route('/api/hosts/<hostname>/supported_install_actions')
@login_required
def api_get_supported_install_actions(hostname):
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is None:
        abort(404)

    rows = []

    if host.family == PlatformFamily.ASR900:
        rows.append({'install_options': [InstallAction.PRE_UPGRADE, InstallAction.INSTALL_ADD,
                                         InstallAction.INSTALL_ACTIVATE, InstallAction.POST_UPGRADE,
                                         InstallAction.ALL]})
        rows.append({'cleanup_options': [InstallAction.INSTALL_REMOVE]})
    else:
        rows.append({'install_options': [InstallAction.PRE_UPGRADE, InstallAction.INSTALL_ADD,
                                         InstallAction.INSTALL_ACTIVATE, InstallAction.POST_UPGRADE,
                                         InstallAction.INSTALL_COMMIT, InstallAction.ALL]})
        rows.append({'cleanup_options': [InstallAction.INSTALL_REMOVE, InstallAction.INSTALL_DEACTIVATE]})
        rows.append({'other_options': [InstallAction.FPD_UPGRADE]})

    return jsonify(**{'data': rows})


def handle_schedule_install_form(request, db_session, hostname, install_job=None):
    host = get_host(db_session, hostname)
    if host is None:
        abort(404)

    return_url = get_return_url(request, 'host_dashboard.home')

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
    fill_servers(form.server_modal_dialog_server.choices, region_servers)
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
        custom_command_profile = ','.join([str(i) for i in form.custom_command_profile.data])
        
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
        form.hidden_selected_hosts.data = ''
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
                           return_url=return_url)


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


@app.route('/api/get_session_logs/table/<table>')
@login_required
def api_get_session_logs(table):
    id = request.args.get("record_id")

    db_session = DBSession()
    if table == 'install_job':
        install_job = db_session.query(InstallJob).filter(InstallJob.id == id).first()
    elif table == 'install_job_history':
        install_job = db_session.query(InstallJobHistory).filter(InstallJobHistory.id == id).first()
    elif table == 'inventory_job_history':
        install_job = db_session.query(InventoryJobHistory).filter(InventoryJobHistory.id == id).first()

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
    return render_template('log.html', system_option=SystemOption.get(DBSession()))


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

    install_job = get_last_completed_install_job_for_install_action(db_session, host_id, InstallAction.INSTALL_ADD)
    if install_job is not None:
        result_list.append(install_job.packages)
    
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

    db_session = DBSession()
    region = get_region_by_id(db_session, region_id)

    return get_nonlocal_servers(db_session, region)


@app.route('/api/get_nonlocal_servers_by_region_name/region/<region_name>')
@login_required
def api_get_nonlocal_servers_by_region_name(region_name):

    db_session = DBSession()
    region = get_region(db_session, region_name)

    return get_nonlocal_servers(db_session, region)


def get_nonlocal_servers(db_session, region):
    result_list = []

    if region is not None and len(region.servers) > 0:
        for server in region.servers:
            if server.server_type != ServerType.LOCAL_SERVER:
                result_list.append({'server_id': server.id, 'hostname': server.hostname})
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
                host_platform_software = UNKNOWN

            if not selected_software or host_platform_software in selected_software:
                row = {'hostname': host.hostname,
                       'roles': host.roles,
                       'platform_software': host_platform_software}

                rows.append(row)
    
    return jsonify(**{'data': rows})


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
    target_packages = get_target_software_package_list(host.family, host.os_type, host_packages,
                                                       target_release, match_internal_name)
    for package in target_packages:
        rows.append({'package' : package})

    return jsonify( **{'data':rows} )


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
                description = ''
                if smu_loader.is_valid:
                    smu_info = smu_loader.get_smu_info(smu_name.replace('.' + smu_loader.file_suffix, ''))
                    description = '' if smu_info is None else smu_info.description
                    # If selected package is on CCO
                    if cco_filename is not None and smu_info.status == 'Posted':
                        rows.append({'smu_entry': smu_name, 'description': description,
                                     'cco_filename': cco_filename, 'is_downloadable': True})
                    else:
                        rows.append({'smu_entry': smu_name, 'description': description,
                                     'is_downloadable': False})
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
        if cco_filename is not None and smu_info.status == 'Posted':
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
    platform, release = SMUInfoLoader.get_platform_and_release(smu_list)
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
        platform, release = SMUInfoLoader.get_platform_and_release(package_list)
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
    smu_name = strip_smu_file_extension(smu_name)
    for package in host_packages:
        # Performs a partial match
        if smu_name in package:
            return True
    return False


# This route will prompt a file download
@app.route('/download_session_log')
@login_required
def download_session_log():
    return send_file(get_log_directory() + request.args.get('file_path'), as_attachment=True)


@app.route('/api/download_session_logs', methods=['POST'])
@login_required
def api_download_session_logs():
    file_list = request.args.getlist('file_list[]')[0].split(',')
    return download_session_logs(file_list)


@app.route('/download_system_logs')
@login_required
def download_system_logs():
    db_session = DBSession()
    logs = db_session.query(Log) \
        .order_by(Log.created_time.desc())
        
    contents = ''
    for log in logs:
        contents += get_datetime_string(log.created_time) + ' UTC\n'
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

if __name__ == '__main__':
    initialize.init()
    app.run(host='0.0.0.0', use_reloader=False, threaded=True, debug=False)
