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
from flask import request
from flask import abort
from flask import jsonify
from flask import render_template

from flask.ext.login import current_user

from wtforms import Form
from wtforms import StringField
from wtforms import HiddenField
from wtforms import SelectMultipleField
from wtforms.validators import required

from sqlalchemy import and_

from database import DBSession

from common import get_host
from common import get_software_profile_by_id
from common import can_delete_install
from common import can_retrieve_software
from common import delete_install_job_dependencies
from common import get_last_successful_inventory_elapsed_time

from models import logger
from models import Package
from models import SystemOption
from models import Satellite
from models import InstallJob
from models import InstallJobHistory
from models import InventoryJobHistory

from forms import HostScheduleInstallForm

from constants import UNKNOWN
from constants import JobStatus
from constants import PackageState
from constants import InstallAction

from flask.ext.login import login_required

from filters import time_difference_UTC

import collections
import datetime

host_dashboard = Blueprint('host_dashboard', __name__, url_prefix='/host_dashboard')


@host_dashboard.route('/hosts/<hostname>/')
@login_required
def home(hostname):
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is None:
        abort(404)

    return render_template('host/host_dashboard.html', host=host,
                           form=get_host_schedule_install_form(request),
                           manage_satellite_software_form=ManageSatelliteSoftwareDialogForm(request.form),
                           satellite_install_action=get_satellite_install_action_dict(),
                           system_option=SystemOption.get(db_session),
                           server_time=datetime.datetime.utcnow(),
                           package_states=[PackageState.ACTIVE_COMMITTED,
                                           PackageState.ACTIVE,
                                           PackageState.INACTIVE_COMMITTED,
                                           PackageState.INACTIVE])


def get_satellite_install_action_dict():
    return {
        'transfer': InstallAction.SATELLITE_TRANSFER,
        'activate': InstallAction.SATELLITE_ACTIVATE
    }

def get_host_schedule_install_form(request):
    return HostScheduleInstallForm(request.form)


@host_dashboard.route('/api/hosts/<hostname>/host_dashboard/cookie')
@login_required
def api_get_host_dashboard_cookie(hostname):
    db_session = DBSession()
    host = get_host(db_session, hostname)

    rows = []
    if host is not None:
        software_profile = get_software_profile_by_id(db_session, host.software_profile_id)
        system_option = SystemOption.get(db_session)
        row = {}
        connection_param = host.connection_param[0]
        row['hostname'] = host.hostname
        row['region'] = host.region.name if host.region is not None else UNKNOWN
        row['location'] = host.location
        row['roles'] = host.roles
        row['platform'] = host.platform
        row['software_platform'] = host.software_platform
        row['software_version'] = host.software_version
        row['host_or_ip'] = connection_param.host_or_ip
        row['username'] = connection_param.username
        row['connection'] = connection_param.connection_type
        row['port_number'] = connection_param.port_number
        row['created_by'] = host.created_by
        row['software_profile_name'] = '' if software_profile is None else software_profile.name

        if connection_param.jump_host is not None:
            row['jump_host'] = connection_param.jump_host.hostname

        # Last inventory successful time
        inventory_job = host.inventory_job[0]
        row['last_successful_inventory_elapsed_time'] = get_last_successful_inventory_elapsed_time(host)
        row['last_successful_inventory_time'] = inventory_job.last_successful_time
        row['status'] = inventory_job.status
        row['can_schedule'] = system_option.can_schedule
        row['can_install'] = system_option.can_install
        rows.append(row)

    return jsonify(**{'data': rows})


@host_dashboard.route('/api/hosts/<hostname>/packages/<package_state>')
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


@host_dashboard.route('/api/hosts/<hostname>/scheduled_installs')
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

            if install_job.data:
                job_info = install_job.data.get('job_info')
                if job_info:
                    row['job_info'] = install_job.id

            rows.append(row)

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


@host_dashboard.route('/api/hosts/<hostname>/software_inventory_history', methods=['GET'])
@login_required
def api_get_host_dashboard_software_inventory_history(hostname):
    rows = []
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is not None:
        inventory_jobs = db_session.query(InventoryJobHistory).filter(InventoryJobHistory.host_id == host.id). \
            order_by(InventoryJobHistory.created_time.desc())

        return jsonify(**get_inventory_job_json_dict(inventory_jobs))

    return jsonify(**{'data': rows})


@host_dashboard.route('/hosts/<hostname>/delete_all_failed_installations/', methods=['DELETE'])
@login_required
def delete_all_failed_installations_for_host(hostname):
    if not can_delete_install(current_user):
        abort(401)

    return delete_all_installations_for_host(hostname=hostname, status=JobStatus.FAILED)


@host_dashboard.route('/hosts/<hostname>/delete_all_scheduled_installations/', methods=['DELETE'])
@login_required
def delete_all_scheduled_installations_for_host(hostname):
    if not can_delete_install(current_user):
        abort(401)

    return delete_all_installations_for_host(hostname)


def delete_all_installations_for_host(hostname, status=JobStatus.SCHEDULED):
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
                delete_install_job_dependencies(db_session, install_job.id)

        db_session.commit()
        return jsonify({'status': 'OK'})
    except:
        logger.exception('delete_install_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@host_dashboard.route('/api/get_inventory/<hostname>')
@login_required
def get_inventory(hostname):
    if not can_retrieve_software(current_user):
        abort(401)

    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is not None:
        if host.inventory_job[0].status not in [JobStatus.SCHEDULED, JobStatus.IN_PROGRESS]:
            host.inventory_job[0].status = JobStatus.SCHEDULED
            db_session.commit()
            return jsonify({'status': 'OK'})

    return jsonify({'status': 'Failed'})


@host_dashboard.route('/api/is_host_valid/<hostname>')
@login_required
def api_is_host_valid(hostname):
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is not None:
        return jsonify({'status': 'OK'})

    return jsonify({'status': 'Failed'})


@host_dashboard.route('/api/hosts/<hostname>/satellites')
@login_required
def api_get_host_satellites(hostname):
    rows = []
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if host is not None:
        satellites = db_session.query(Satellite).filter(Satellite.host_id == host.id)
        for satellite in satellites:
            if satellite.state == 'Connected' and \
                    "Available" in satellite.remote_version_details:
                row = dict()
                row['satellite_id'] = satellite.satellite_id
                row['type'] = satellite.type
                row['state'] = satellite.state
                row['install_state'] = satellite.install_state
                row['ip_address'] = satellite.ip_address
                row['mac_address'] = satellite.mac_address
                row['serial_number'] = satellite.serial_number
                row['remote_version'] = satellite.remote_version
                row['remote_version_details'] = satellite.remote_version_details
                row['fabric_links'] = satellite.fabric_links
                rows.append(row)

    return jsonify(**{'data': rows})


@host_dashboard.route('/api/hosts/<hostname>/get_satellite_count')
@login_required
def api_get_satellite_count(hostname):
    db_session = DBSession()

    satellite_count = 0
    host = get_host(db_session, hostname)
    if host is not None:
        satellite_count = db_session.query(Satellite).filter(Satellite.host_id == host.id).count()

    return jsonify(**{'data': {'satellite_count': satellite_count}})


class ManageSatelliteSoftwareDialogForm(Form):
    satellite_install_action = SelectMultipleField('Install Action', coerce=str, choices=[('', '')])
    satellite_scheduled_time = StringField('Scheduled Time', [required()])
    satellite_pre_check_script = StringField('Pre-Check Script')
    satellite_post_check_script = StringField('Post-Check Script')
    satellite_scheduled_time_UTC = HiddenField('Scheduled Time')
