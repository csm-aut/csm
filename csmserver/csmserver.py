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
from flask import request
from flask import Response
from flask import redirect
from flask import url_for
from flask_login import LoginManager
from flask_login import current_user
from flask_login import login_required

from werkzeug.contrib.fixers import ProxyFix

from sqlalchemy import and_

from database import DBSession

from models import Host
from models import logger
from models import Region
from models import User

from constants import ServerType
from constants import UNKNOWN

from common import get_host
from common import get_host_list
from common import get_server_list
from common import get_region
from common import get_region_by_id
from common import get_host_list_by

from utils import is_empty
from utils import get_build_date

from restful import restful_api

from views.home import home
from views.cco import cco
from views.log import log
from views.install import install
from views.authenticate import authenticate
from views.asr9k_x64_migrate import asr9k_x64_migrate
from views.conformance import conformance
from views.inventory import inventory, update_select2_options
from views.tools import tools
from views.host_import import host_import
from views.custom_command import custom_command
from views.datatable import datatable
from views.host_dashboard import host_dashboard
from views.install_dashboard import install_dashboard
from views.download_dashboard import download_dashboard
from views.admin_console import admin_console

import logging
import filters
import initialize

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

app.register_blueprint(home)
app.register_blueprint(cco)
app.register_blueprint(log)
app.register_blueprint(install)
app.register_blueprint(authenticate)
app.register_blueprint(restful_api)
app.register_blueprint(asr9k_x64_migrate)
app.register_blueprint(conformance)
app.register_blueprint(inventory)
app.register_blueprint(tools)
app.register_blueprint(host_import)
app.register_blueprint(custom_command)
app.register_blueprint(datatable)
app.register_blueprint(host_dashboard)
app.register_blueprint(install_dashboard)
app.register_blueprint(download_dashboard)
app.register_blueprint(admin_console)

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


@app.route('/api/get_hostnames/')
@login_required
def api_get_hostnames():
    """
    This method is called by ajax attached to Select2 (Search a host).
    The returned JSON contains the predefined tags.
    """
    return update_select2_options(request.args, Host.hostname)


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
    rows = []
    db_session = DBSession()

    hosts = get_host_list_by(db_session, platform, software_versions.split(','), region_ids.split(','), roles.split(','))

    for host in hosts:
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


if __name__ == '__main__':
    initialize.init()
    app.run(host='0.0.0.0', use_reloader=False, threaded=True, debug=False)
