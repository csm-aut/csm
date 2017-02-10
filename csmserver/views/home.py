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
from flask import request
from flask import redirect
from flask import url_for
from flask import jsonify
from flask import abort
from flask.ext.login import login_required
from flask.ext.login import current_user

from database import DBSession

from common import get_host
from common import get_server
from common import get_jump_host_list
from common import get_region_list
from common import get_server_list
from common import fill_servers
from common import fill_regions
from common import fill_jump_hosts
from common import delete_host
from common import create_or_update_host
from common import create_or_update_jump_host
from common import delete_jump_host
from common import get_jump_host
from common import can_create
from common import can_edit
from common import can_delete
from common import create_or_update_server_repository
from common import delete_server_repository
from common import delete_region
from common import create_or_update_region
from common import get_region
from common import get_server_by_id
from common import get_region_by_id
from common import can_check_reachability
from common import get_jump_host_by_id
from common import fill_software_profiles

from utils import remove_extra_spaces
from utils import is_empty
from utils import get_return_url
from utils import get_build_date
from utils import trim_last_slash
from utils import make_url

from models import Server
from models import SystemOption

from forms import HostForm
from forms import JumpHostForm
from forms import ServerForm
from forms import RegionForm
from forms import BrowseServerDialogForm

from models import logger
from models import Host
from models import Region
from models import System

from constants import UNKNOWN
from constants import ServerType
from constants import ConnectionType
from constants import DefaultHostAuthenticationChoice

from filters import time_difference_UTC

from validate import is_connection_valid
from validate import is_reachable

from server_helper import get_server_impl

import datetime

home = Blueprint('home', __name__, url_prefix='/home')


@home.route('/')
@login_required
def dashboard():
    db_session = DBSession()

    jump_hosts = get_jump_host_list(db_session)
    regions = get_region_list(db_session)
    servers = get_server_list(db_session)

    form = BrowseServerDialogForm(request.form)
    fill_servers(form.dialog_server.choices, get_server_list(DBSession()), False)

    return render_template('host/home.html', form=form,
                           jump_hosts=jump_hosts, regions=regions,
                           servers=servers, system_option=SystemOption.get(db_session),
                           build_date=get_build_date(), current_user=current_user)


@home.route('/api/get_server_time')
@login_required
def api_get_server_time():
    dict = {}
    db_session = DBSession()
    system = db_session.query(System).first()
    start_time = system.start_time

    dict['server_time'] = datetime.datetime.utcnow()
    dict['uptime'] = time_difference_UTC(start_time).strip(' ago')

    return jsonify(**{'data': dict})


@home.route('/hosts/create/', methods=['GET', 'POST'])
@login_required
def host_create():
    if not can_create(current_user):
        abort(401)

    form = HostForm(request.form)

    db_session = DBSession()
    fill_jump_hosts(db_session, form.jump_host.choices)
    fill_regions(db_session, form.region.choices)
    fill_software_profiles(db_session, form.software_profile.choices)

    if request.method == 'POST' and form.validate():
        db_session = DBSession()
        try:
            host = get_host(db_session, form.hostname.data)
            if host is not None:
                return render_template('host/edit.html', form=form, duplicate_error=True)

            create_or_update_host(db_session=db_session, hostname=form.hostname.data, region_id=form.region.data,
                                  location=form.location.data, roles=form.roles.data,
                                  software_profile_id=form.software_profile.data,
                                  connection_type=form.connection_type.data,
                                  host_or_ip=form.host_or_ip.data, username=form.username.data,
                                  password=form.password.data, enable_password=form.enable_password.data,
                                  port_number=form.port_number.data, jump_host_id=form.jump_host.data,
                                  created_by=current_user.username)

        finally:
            db_session.rollback()

        return redirect(url_for('home'))

    return render_template('host/edit.html', form=form)


@home.route('/hosts/<hostname>/edit/', methods=['GET', 'POST'])
@login_required
def host_edit(hostname):
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is None:
        abort(404)

    form = HostForm(request.form)
    fill_jump_hosts(db_session, form.jump_host.choices)
    fill_regions(db_session, form.region.choices)
    fill_software_profiles(db_session, form.software_profile.choices)

    if request.method == 'POST' and form.validate():
        if not can_edit(current_user):
            abort(401)

        # Editing a hostname which has already existed in the database.
        if hostname != form.hostname.data and get_host(db_session, form.hostname.data) is not None:
            return render_template('host/edit.html', form=form, duplicate_error=True)

        create_or_update_host(db_session=db_session, hostname=form.hostname.data, region_id=form.region.data,
                              location=form.location.data, roles=form.roles.data,
                              software_profile_id=form.software_profile.data,
                              connection_type=form.connection_type.data,
                              host_or_ip=form.host_or_ip.data, username=form.username.data,
                              password=form.password.data
                              if len(form.password.data) > 0 else host.connection_param[0].password,
                              enable_password=form.enable_password.data
                              if len(form.enable_password.data) > 0 else host.connection_param[0].enable_password,
                              port_number=form.port_number.data, jump_host_id=form.jump_host.data,
                              created_by=current_user.username, host=host)

        return_url = get_return_url(request, 'home')

        if return_url is None:
            return redirect(url_for('home'))
        else:
            return redirect(url_for(return_url, hostname=hostname))
    else:
        # Assign the values to form fields
        form.hostname.data = host.hostname
        form.region.data = host.region_id
        form.software_profile.data = host.software_profile_id
        form.location.data = host.location
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


@home.route('/hosts/<hostname>/delete/', methods=['DELETE'])
@login_required
def host_delete(hostname):
    if not can_delete(current_user):
        abort(401)

    db_session = DBSession()

    try:
        delete_host(db_session, hostname)
    except:
        logger.exception('delete_host hit exception')
        abort(404)

    return jsonify({'status': 'OK'})


@home.route('/jump_hosts/create/', methods=['GET', 'POST'])
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

        create_or_update_jump_host(db_session=db_session,
                                   hostname=form.hostname.data,
                                   host_or_ip=form.host_or_ip.data,
                                   username=form.username.data,
                                   password=form.password.data,
                                   connection_type=form.connection_type.data,
                                   port_number=form.port_number.data,
                                   created_by=current_user.username)

        return redirect(url_for('home'))

    return render_template('jump_host/edit.html', form=form)


@home.route('/jump_hosts/<hostname>/edit/', methods=['GET', 'POST'])
@login_required
def jump_host_edit(hostname):
    db_session = DBSession()

    jump_host = get_jump_host(db_session, hostname)
    if jump_host is None:
        abort(404)

    form = JumpHostForm(request.form, jump_host)

    if request.method == 'POST' and form.validate():
        if not can_edit(current_user):
            abort(401)

        if hostname != form.hostname.data and get_jump_host(db_session, form.hostname.data) is not None:
            return render_template('jump_host/edit.html', form=form, duplicate_error=True)

        create_or_update_jump_host(db_session=db_session,
                                   hostname=form.hostname.data,
                                   host_or_ip=form.host_or_ip.data,
                                   username=form.username.data,
                                   password=form.password.data if len(form.password.data) > 0 else jump_host.password,
                                   connection_type=form.connection_type.data,
                                   port_number=form.port_number.data,
                                   created_by=current_user.username,
                                   jumphost=jump_host)

        return redirect(url_for('home'))
    else:
        # Assign the values to form fields
        form.hostname.data = jump_host.hostname
        form.host_or_ip.data = jump_host.host_or_ip
        form.username.data = jump_host.username
        form.connection_type.data = jump_host.connection_type
        form.port_number.data = jump_host.port_number
        if not is_empty(jump_host.password):
            form.password_placeholder = 'Use Password on File'
        else:
            form.password_placeholder = 'No Password Specified'

        return render_template('jump_host/edit.html', form=form)


@home.route('/jump_hosts/<hostname>/delete/', methods=['DELETE'])
@login_required
def jump_host_delete(hostname):
    if not can_delete(current_user):
        abort(401)

    db_session = DBSession()

    try:
        delete_jump_host(db_session, hostname)
        return jsonify({'status': 'OK'})
    except:
        abort(404)


@home.route('/servers/create/', methods=['GET', 'POST'])
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

        create_or_update_server_repository(db_session=db_session,
                                           hostname=form.hostname.data,
                                           server_type=form.server_type.data,
                                           server_url=trim_last_slash(form.server_url.data),
                                           username=form.username.data,
                                           password=form.password.data,
                                           vrf=form.vrf.data if form.server_type.data == ServerType.TFTP_SERVER or
                                                                form.server_type.data == ServerType.FTP_SERVER else '',
                                           server_directory=trim_last_slash(form.server_directory.data),
                                           destination_on_host=form.destination_on_host.data,
                                           created_by=current_user.username)

        return redirect(url_for('home'))

    return render_template('server/edit.html', form=form)


@home.route('/servers/<hostname>/edit/', methods=['GET', 'POST'])
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

        create_or_update_server_repository(db_session=db_session,
                                           hostname=form.hostname.data,
                                           server_type=form.server_type.data,
                                           server_url=trim_last_slash(form.server_url.data),
                                           username=form.username.data,
                                           password=form.password.data if len(form.password.data) > 0 else server.password,
                                           vrf=form.vrf.data if form.server_type.data == ServerType.TFTP_SERVER or
                                                                form.server_type.data == ServerType.FTP_SERVER else '',
                                           server_directory=trim_last_slash(form.server_directory.data),
                                           destination_on_host=form.destination_on_host.data,
                                           created_by=current_user.username,
                                           server=server)

        return redirect(url_for('home'))
    else:
        # Assign the values to form fields
        form.hostname.data = server.hostname
        form.server_type.data = server.server_type
        form.server_url.data = server.server_url
        form.username.data = server.username
        form.vrf.data = server.vrf
        form.server_directory.data = server.server_directory
        form.destination_on_host.data = server.destination_on_host

        if not is_empty(server.password):
            form.password_placeholder = 'Use Password on File'
        else:
            form.password_placeholder = 'No Password Specified'

        return render_template('server/edit.html', form=form)


@home.route('/servers/<hostname>/delete/', methods=['DELETE'])
@login_required
def server_delete(hostname):
    if not can_delete(current_user):
        abort(401)

    db_session = DBSession()
    try:
        delete_server_repository(db_session, hostname)
        return jsonify({'status': 'OK'})
    except:
        return jsonify({'status': 'Failed'})


@home.route('/regions/create/', methods=['GET', 'POST'])
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

        # Compose a list of server hostnames
        server_names = [get_server_by_id(db_session, id).hostname for id in request.form.getlist('selected-servers')]

        try:
            create_or_update_region(db_session=db_session,
                                    region_name=form.region_name.data,
                                    server_repositories=",".join(server_names),
                                    created_by=current_user.username)
        except Exception as e:
            db_session.rollback()
            logger.exception("region_create() encountered an exception: " + e.message)

        return redirect(url_for('home'))

    return render_template('region/edit.html', form=form)


@home.route('/regions/<region_name>/edit/', methods=['GET', 'POST'])
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

        # Compose a list of server hostnames
        server_names = [get_server_by_id(db_session, id).hostname for id in request.form.getlist('selected-servers')]

        try:
            create_or_update_region(db_session=db_session,
                                    region_name=form.region_name.data,
                                    server_repositories=','.join(server_names),
                                    created_by=current_user.username,
                                    region=get_region(db_session, region_name))
        except Exception as e:
            db_session.rollback()
            logger.exception("region_edit() encountered an exception: " + e.message)

        return redirect(url_for('home'))
    else:
        form.region_name.data = region.name

        return render_template('region/edit.html', form=form, region=region)


@home.route('/regions/<region_name>/delete/', methods=['DELETE'])
@login_required
def region_delete(region_name):
    if not can_delete(current_user):
        abort(401)

    db_session = DBSession()

    try:
        delete_region(db_session, region_name)
        return jsonify({'status': 'OK'})
    except:
        return jsonify({'status': 'Failed'})


@home.route('/api/get_host_platform_version/region/<int:region_id>')
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
            platform = UNKNOWN if host.software_platform is None else host.software_platform
            software = UNKNOWN if host.software_version is None else host.software_version

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


@home.route('/api/get_host_and_region_counts')
@login_required
def get_host_and_region_counts():
    db_session = DBSession()

    total_host_count = db_session.query(Host).count()
    total_region_count = db_session.query(Region).count()

    return jsonify(**{'data': [{'total_host_count': total_host_count, 'total_region_count': total_region_count}]})


@home.route('/api/get_region_name/region/<int:region_id>')
@login_required
def get_region_name(region_id):
    region_name = 'ALL'
    db_session = DBSession()

    if region_id > 0:
        region = get_region_by_id(db_session, region_id)
        if region is not None:
            region_name = region.name

    return jsonify(**{'data': [{'region_name': region_name}]})


@home.route('/api/get_regions/')
@login_required
def api_get_regions():
    """
    This method is called by ajax attached to Select2 in home page.
    The returned JSON contains the predefined tags.
    """
    db_session = DBSession()

    rows = []
    criteria = '%'
    if request.args and request.args.get('q'):
        criteria += request.args.get('q') + '%'
    else:
        criteria += '%'

    regions = db_session.query(Region).filter(Region.name.like(criteria)).order_by(Region.name.asc()).all()
    if len(regions) > 0:
        if request.args.get('show_all'):
            rows.append({'id': 0, 'text': 'ALL'})
        for region in regions:
            rows.append({'id': region.id, 'text': region.name})

    return jsonify(**{'data': rows})


@home.route('/api/check_host_reachability')
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


@home.route('/api/check_jump_host_reachability')
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


@home.route('/api/check_server_reachability')
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
    if (server_type == ServerType.FTP_SERVER or
        server_type == ServerType.SFTP_SERVER or
        server_type == ServerType.SCP_SERVER) and password == '':

        db_session = DBSession()
        server_in_db = get_server(db_session, hostname)
        if server_in_db is not None:
            server.password = server_in_db.password

    server_impl = get_server_impl(server)

    is_reachable, error = server_impl.check_reachability()

    if is_reachable:
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': error})


@home.route('/api/hosts/<hostname>/password', methods=['DELETE'])
def api_remove_host_password(hostname):
    return remove_host_password(hostname)


@home.route('/api/hosts/<hostname>/enable_password', methods=['DELETE'])
def api_remove_host_enable_password(hostname):
    return remove_host_enable_password(hostname)


def remove_host_password(hostname):
    if not can_create(current_user):
        abort(401)

    db_session = DBSession()
    host = get_host(db_session, hostname)

    if host is not None:
        host.connection_param[0].password = ''
        db_session.commit()

        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


def remove_host_enable_password(hostname):
    if not can_create(current_user):
        abort(401)

    db_session = DBSession()
    host = get_host(db_session, hostname)

    if host is not None:
        host.connection_param[0].enable_password = ''
        db_session.commit()

        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


@home.route('/api/jump_hosts/<hostname>/password', methods=['DELETE'])
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
