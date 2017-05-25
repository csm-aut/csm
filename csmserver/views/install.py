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
from flask import abort
from flask import render_template
from flask import request
from flask import jsonify
from flask import redirect
from flask import url_for

from sqlalchemy import and_

from database import DBSession

from models import InstallJob
from models import Server
from models import SystemOption
from models import Package
from models import InstallJobHistory

from common import get_host
from common import can_install
from common import get_server_list
from common import fill_servers
from common import get_server_by_id
from common import fill_custom_command_profiles
from common import create_or_update_install_job
from common import get_last_install_action
from common import fill_dependencies
from common import fill_dependency_from_host_install_jobs
from common import fill_regions
from common import can_edit_install
from common import get_host_active_packages
from common import can_retrieve_software
from common import get_last_successful_inventory_elapsed_time

from forms import ScheduleInstallForm
from forms import HostScheduleInstallForm

from flask.ext.login import login_required
from flask.ext.login import current_user

from constants import JobStatus
from constants import PlatformFamily
from constants import InstallAction

from utils import is_empty
from utils import get_return_url

from filters import get_datetime_string

from server_helper import get_server_impl

from smu_utils import get_smu_info_dict
from smu_utils import get_peer_packages
from smu_utils import get_missing_prerequisite_list

from smu_info_loader import SMUInfoLoader

from package_utils import strip_smu_file_extension
from package_utils import get_target_software_package_list

import datetime

install = Blueprint('install', __name__, url_prefix='/install')


@install.route('/hosts/<hostname>/schedule_install/', methods=['GET', 'POST'])
@login_required
def host_schedule_install(hostname):
    """
    Individual host schedule install
    """
    if not can_install(current_user):
        abort(401)

    return handle_schedule_install_form(request=request, db_session=DBSession(), hostname=hostname)


@install.route('/hosts/<hostname>/schedule_install/<int:id>/edit/', methods=['GET', 'POST'])
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
    fill_custom_command_profiles(db_session, form.custom_command_profile.choices)

    if request.method == 'POST':
        if install_job is not None:
            # In Edit mode, the install_action UI on HostScheduleForm is disabled (not allow to change).
            # Thus, there will be no value returned by form.install_action.data.  So, re-use the existing ones.
            install_action = [install_job.install_action]
        else:
            install_action = form.install_action.data

        scheduled_time = form.scheduled_time_UTC.data
        software_packages = form.software_packages.data.split()
        server_id = form.hidden_server.data
        server_directory = form.hidden_server_directory.data
        pending_downloads = form.hidden_pending_downloads.data.split()
        custom_command_profile_ids = [str(i) for i in form.custom_command_profile.data]

        # install_action is a list object which may contain multiple install actions.
        # If only one install_action, accept the selected dependency if any
        if len(install_action) == 1:
            dependency = int(form.dependency.data)
            create_or_update_install_job(db_session=db_session, host_id=host.id, install_action=install_action[0],
                                         scheduled_time=scheduled_time, software_packages=software_packages,
                                         server_id=server_id, server_directory=server_directory,
                                         pending_downloads=pending_downloads,
                                         custom_command_profile_ids=custom_command_profile_ids, dependency=dependency,
                                         created_by=current_user.username, install_job=install_job)
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
                                                               software_packages=software_packages, server_id=server_id,
                                                               server_directory=server_directory,
                                                               pending_downloads=pending_downloads,
                                                               custom_command_profile_ids=custom_command_profile_ids,
                                                               dependency=dependency, created_by=current_user.username,
                                                               install_job=install_job)
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

            if install_job.custom_command_profile_ids:
                ids = [int(id) for id in install_job.custom_command_profile_ids.split(',')]
                form.custom_command_profile.data = ids

    return render_template('host/schedule_install.html', form=form, system_option=SystemOption.get(db_session),
                           host=host, server_time=datetime.datetime.utcnow(), install_job=install_job,
                           return_url=return_url)


@install.route('/batch_schedule_install/', methods=['GET', 'POST'])
@login_required
def batch_schedule_install():
    """
    For batch scheduled installation.
    """
    if not can_install(current_user):
        abort(401)

    db_session = DBSession()
    form = ScheduleInstallForm(request.form)

    # Fills the selections
    fill_regions(db_session, form.region.choices)
    fill_dependencies(form.dependency.choices)
    fill_custom_command_profiles(db_session, form.custom_command_profile.choices)

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

        custom_command_profile_ids = [str(i) for i in form.custom_command_profile.data]

        if hostnames is not None:

            for hostname in hostnames:
                host = get_host(db_session, hostname)
                if host is not None:
                    db_session = DBSession()
                    scheduled_time = form.scheduled_time_UTC.data
                    software_packages = form.software_packages.data.split()
                    server_id = form.hidden_server.data
                    server_directory = form.hidden_server_directory.data
                    pending_downloads = form.hidden_pending_downloads.data.split()

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
                                                     custom_command_profile_ids=custom_command_profile_ids,
                                                     scheduled_time=scheduled_time, software_packages=software_packages,
                                                     server_id=server_id, server_directory=server_directory,
                                                     pending_downloads=pending_downloads, dependency=dependency,
                                                     created_by=current_user.username)
                    else:
                        # The dependency on each install action is already indicated in the implicit ordering
                        # in the selector.  If the user selected Pre-Upgrade and Install Add, Install Add (successor)
                        # will have Pre-Upgrade (predecessor) as the dependency.
                        dependency = 0
                        for one_install_action in install_action:
                            new_install_job = create_or_update_install_job(db_session=db_session, host_id=host.id,
                                                                           install_action=one_install_action,
                                                                           scheduled_time=scheduled_time,
                                                                           custom_command_profile_ids=custom_command_profile_ids,
                                                                           software_packages=software_packages,
                                                                           server_id=server_id,
                                                                           server_directory=server_directory,
                                                                           pending_downloads=pending_downloads,
                                                                           dependency=dependency,
                                                                           created_by=current_user.username)
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


def is_smu_on_server_repository(server_file_dict, smu_name):
    for file_info in server_file_dict:
        if not file_info['is_directory'] and file_info['filename'] == smu_name:
            return True
    return False


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


@install.route('/api/get_server_file_dict/<int:server_id>')
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


@install.route('/api/get_missing_files_on_server/<int:server_id>')
@login_required
def api_get_missing_files_on_server(server_id):
    """
    Given a package list, return the ones that are missing in the server repository.
    """
    rows = []
    package_list = request.args.get('package_list').split()
    server_directory = request.args.get('server_directory')

    server_file_dict, is_reachable = get_server_file_dict(server_id, server_directory)
    if is_reachable:
        smu_loader = SMUInfoLoader.get_loader_from_package(package_list)
        if smu_loader.is_valid:
            smu_info_dict = get_smu_info_dict(DBSession(), smu_loader, package_list)

            for package_name, smu_info in smu_info_dict.items():
                if not is_smu_on_server_repository(server_file_dict, package_name):
                    if smu_info is None:
                        rows.append({'smu_entry': package_name, 'description': '', 'is_downloadable': False})
                    else:
                        # If selected package is on CCO
                        if smu_info.status == 'Posted':
                            rows.append({'smu_entry': package_name, 'description': smu_info.description,
                                         'cco_filename': smu_info.cco_filename, 'is_downloadable': True})
                        else:
                            rows.append({'smu_entry': package_name, 'description': smu_info.description,
                                         'is_downloadable': False})
        else:
            for package_name in package_list:
                if not is_smu_on_server_repository(server_file_dict, package_name):
                    rows.append({'smu_entry': package_name, 'description': '', 'is_downloadable': False})
    else:
        return jsonify({'status': 'Failed'})

    return jsonify(**{'data': rows})


def host_packages_contains(host_packages, smu_name):
    smu_name = strip_smu_file_extension(smu_name).replace('.x86_64', '')
    for package in host_packages:
        # Performs a partial match
        if smu_name in package:
            return True
    return False


@install.route('/api/get_missing_prerequisite_list')
@login_required
def api_get_missing_prerequisite_list():
    """
    Given a package list, return the missing pre-requisities.
    An example of a package list:
        asr9k-px-6.1.3.CSCvd54775.pie
        ncs5500-k9sec-2.2.0.2-r613.CSCvd18741.x86_64.rpm
    """
    hostname = request.args.get('hostname')
    package_list = request.args.get('package_list').split()

    rows = []
    db_session = DBSession()
    missing_peer_packages_dict = dict()
    smu_loader = SMUInfoLoader.get_loader_from_package(package_list)

    if smu_loader.is_valid:
        smu_info_dict = get_smu_info_dict(DBSession(), smu_loader, package_list)

        smu_name_set = set()
        for package_name, smu_info in smu_info_dict.items():
            if smu_info is not None:
                smu_name_set.add(smu_info.name)
                # On eXR platforms, a SMU may contain multiple RPMs.  Not only does CSM need
                # to check for missing pre-requisite, but also missing peers in the same SMU.
                peer_package_list = get_peer_packages(db_session, smu_loader, package_name)
                for peer_package_name in peer_package_list:
                    # if peer_package is not in the original package_list. Add it.
                    if peer_package_name not in package_list:
                        missing_peer_packages_dict[peer_package_name] = smu_info.description

        prerequisite_list = get_missing_prerequisite_list(smu_loader, list(smu_name_set))
        host_packages = get_host_active_packages(hostname)

        # smu_name examples: asr9k-px-6.1.3.CSCvd54775, ncs5500-6.1.3.CSCvd18741
        for smu_name in prerequisite_list:
            smu_info = smu_loader.get_smu_info(smu_name)
            if smu_info is not None:
                description = smu_info.description

                # If the missing pre-requisites have not been installed
                # (i.e. not in the Active/Active-Committed), include them.
                if not is_empty(smu_info.package_names):
                    for package_name in smu_info.package_names.split(','):
                        # FIXME: Need reviewing the code in this method
                        if not host_packages_contains(host_packages, package_name):
                            rows.append({'smu_entry': package_name, 'description': description})

        # add the missing peer packages
        for peer_package_name, description in missing_peer_packages_dict.items():
            if not host_packages_contains(host_packages, peer_package_name):
                rows.append({'smu_entry': peer_package_name, 'description': description})

    return jsonify(**{'data': rows})


@install.route('/api/get_reload_list')
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
        smu_loader = SMUInfoLoader.get_loader_from_package(package_list)
        smu_info_dict = get_smu_info_dict(DBSession(), smu_loader, package_list)

        for package_name, smu_info in smu_info_dict.items():
            if any(s in package_name for s in ['mini']):
                rows.append({'entry': package_name, 'description': ''})
            else:
                if smu_info is not None:
                    if any(s in smu_info.impact for s in ['Reload', 'Reboot']):
                        rows.append({'entry': package_name, 'description': smu_info.description})

    return jsonify(**{'data': rows})


@install.route('/api/hosts/<hostname>/supported_install_actions')
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
        rows.append({'cleanup_options': [InstallAction.INSTALL_REMOVE, InstallAction.INSTALL_REMOVE_ALL_INACTIVE,
                                         InstallAction.INSTALL_DEACTIVATE]})
        rows.append({'other_options': [InstallAction.FPD_UPGRADE]})

    return jsonify(**{'data': rows})


@install.route('/api/get_install_history/hosts/<hostname>')
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
                        InstallJobHistory.status == JobStatus.COMPLETED)).\
            order_by(InstallJobHistory.status_time.desc())

        for install_job in install_jobs:
            if not is_empty(install_job.packages):
                row = {}
                row['packages'] = install_job.packages
                row['status_time'] = install_job.status_time
                row['created_by'] = install_job.created_by
                rows.append(row)

    return jsonify(**{'data': rows})


@install.route('/api/get_software_package_upgrade_list/hosts/<hostname>/release/<target_release>')
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
        rows.append({'package': package})

    return jsonify(**{'data': rows})


@install.route('/api/hosts/<hostname>/last_successful_inventory_elapsed_time/')
@login_required
def api_get_last_successful_inventory_elapsed_time(hostname):
    db_session = DBSession()
    host = get_host(db_session, hostname)
    if host is None:
        abort(404)

    return jsonify(**{'data': [
        {'last_successful_inventory_elapsed_time': get_last_successful_inventory_elapsed_time(host),
         'inventory_retrieval_status': host.inventory_job[0].status}
    ]})


@install.route('/api/hosts/<hostname>/packages')
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
