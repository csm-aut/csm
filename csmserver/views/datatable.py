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
from flask import jsonify
from flask import abort

from sqlalchemy import or_, and_

from flask.ext.login import login_required

from database import DBSession

from inventory import query_available_inventory
from inventory import query_in_use_inventory

from models import Host
from models import HostInventory
from models import Inventory
from models import Region
from models import JumpHost
from models import ConnectionParam
from models import logger
from models import InstallJob
from models import InstallJobHistory

from common import get_host
from common import get_last_successful_inventory_elapsed_time

from constants import UNKNOWN
from constants import JobStatus

from utils import is_empty

from install_dashboard import get_install_job_json_dict

datatable = Blueprint('datatable', __name__, url_prefix='/datatable')


class DataTableParams(object):
    def __init__(self, request):
        self.draw = int(request.args.get('draw'))
        self.search_value = request.args.get('search[value]')
        self.start_length = int(request.args.get('start'))
        self.display_length = int(request.args.get('length'))
        self.sort_order = request.args.get('order[0][dir]')
        self.column_order = int(request.args.get('order[0][column]'))


@datatable.route('/api/get_managed_hosts/region/<int:region_id>')
@login_required
def get_server_managed_hosts(region_id):
    dt_params = DataTableParams(request)

    rows = []
    db_session = DBSession()

    clauses = []
    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(Host.hostname.like(criteria))
        clauses.append(Region.name.like(criteria))
        clauses.append(ConnectionParam.host_or_ip.like(criteria))
        clauses.append(Host.platform.like(criteria))
        clauses.append(Host.software_platform.like(criteria))
        clauses.append(Host.software_version.like(criteria))

    query = db_session.query(Host)\
        .join(Region, Host.region_id == Region.id)\
        .join(ConnectionParam, Host.id == ConnectionParam.host_id)\

    if region_id == 0:
        query = query.filter(or_(*clauses))
        total_count = db_session.query(Host).count()
    else:
        query = query.filter(and_(Host.region_id == region_id), or_(*clauses))
        total_count = db_session.query(Host).filter(Host.region_id == region_id).count()

    filtered_count = query.count()

    columns = [getattr(Host.hostname, dt_params.sort_order)(),
               getattr(Region.name, dt_params.sort_order)(),
               getattr(ConnectionParam.host_or_ip, dt_params.sort_order)(),
               getattr(Host.platform, dt_params.sort_order)(),
               getattr(Host.software_platform, dt_params.sort_order)(),
               getattr(Host.software_version, dt_params.sort_order)()]

    hosts = query.order_by(columns[dt_params.column_order])\
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    if hosts is not None:
        for host in hosts:
            row = dict()
            row['hostname'] = host.hostname
            row['region'] = '' if host.region is None else host.region.name

            if len(host.connection_param) > 0:
                row['host_or_ip'] = host.connection_param[0].host_or_ip
                row['chassis'] = host.platform
                row['platform'] = UNKNOWN if host.software_platform is None else host.software_platform
                row['software'] = UNKNOWN if host.software_version is None else host.software_version

                inventory_job = host.inventory_job[0]
                if inventory_job is not None:
                    row['last_successful_retrieval'] = get_last_successful_inventory_elapsed_time(host)
                    row['inventory_status'] = inventory_job.status
                else:
                    row['last_successful_retrieval'] = ''
                    row['inventory_status'] = ''

                rows.append(row)
            else:
                logger.error('Host %s has no connection information.', host.hostname)

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response['data'] = rows

    return jsonify(**response)


@datatable.route('/api/get_managed_host_details/region/<int:region_id>')
@login_required
def get_managed_host_details(region_id):
    dt_params = DataTableParams(request)

    rows = []
    db_session = DBSession()

    clauses = []
    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(Host.hostname.like(criteria))
        clauses.append(Region.name.like(criteria))
        clauses.append(Host.platform.like(criteria))
        clauses.append(Host.software_platform.like(criteria))
        clauses.append(Host.software_version.like(criteria))
        clauses.append(ConnectionParam.connection_type.like(criteria))
        clauses.append(ConnectionParam.host_or_ip.like(criteria))
        clauses.append(ConnectionParam.port_number.like(criteria))
        clauses.append(ConnectionParam.username.like(criteria))
        clauses.append(JumpHost.hostname.like(criteria))

    query = db_session.query(Host)\
        .join(Region, Host.region_id == Region.id)\
        .join(ConnectionParam, Host.id == ConnectionParam.host_id)\
        .outerjoin(JumpHost, ConnectionParam.jump_host_id == JumpHost.id)\

    if region_id == 0:
        query = query.filter(or_(*clauses))
        total_count = db_session.query(Host).count()
    else:
        query = query.filter(and_(Host.region_id == region_id), or_(*clauses))
        total_count = db_session.query(Host).filter(Host.region_id == region_id).count()

    filtered_count = query.count()

    columns = [getattr(Host.hostname, dt_params.sort_order)(),
               getattr(Region.name, dt_params.sort_order)(),
               getattr(Host.platform, dt_params.sort_order)(),
               getattr(Host.software_platform, dt_params.sort_order)(),
               getattr(Host.software_version, dt_params.sort_order)(),
               getattr(ConnectionParam.connection_type, dt_params.sort_order)(),
               getattr(ConnectionParam.host_or_ip, dt_params.sort_order)(),
               getattr(ConnectionParam.port_number, dt_params.sort_order)(),
               getattr(ConnectionParam.username, dt_params.sort_order)(),
               getattr(JumpHost.hostname, dt_params.sort_order)()]

    hosts = query.order_by(columns[dt_params.column_order])\
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    if hosts is not None:
        for host in hosts:
            row = dict()
            row['hostname'] = host.hostname
            row['region'] = '' if host.region is None else host.region.name
            row['chassis'] = host.platform
            row['platform'] = UNKNOWN if host.software_platform is None else host.software_platform
            row['software'] = UNKNOWN if host.software_version is None else host.software_version

            if len(host.connection_param) > 0:
                connection_param = host.connection_param[0]
                row['connection'] = connection_param.connection_type
                row['host_or_ip'] = connection_param.host_or_ip
                row['port_number'] = connection_param.port_number

                if not is_empty(connection_param.jump_host):
                    row['jump_host'] = connection_param.jump_host.hostname
                else:
                    row['jump_host'] = ''

                row['username'] = connection_param.username

                rows.append(row)
            else:
                logger.error('Host %s has no connection information.', host.hostname)

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response['data'] = rows

    return jsonify(**response)


@datatable.route('/api/get_scheduled_install_jobs/')
@login_required
def api_get_scheduled_install_jobs():
    dt_params = DataTableParams(request)
    db_session = DBSession()

    clauses = []
    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(Host.hostname.like(criteria))
        clauses.append(InstallJob.install_action.like(criteria))
        clauses.append(InstallJob.scheduled_time.like(criteria))
        clauses.append(InstallJob.packages.like(criteria))
        clauses.append(InstallJob.created_by.like(criteria))

    query = db_session.query(InstallJob)\
        .join(Host, Host.id == InstallJob.host_id)

    total_count = query.filter(InstallJob.status == None).count()
    filtered_count = query.filter(and_(InstallJob.status == None), or_(*clauses)).count()

    columns = [getattr(Host.hostname, dt_params.sort_order)(),
               getattr(InstallJob.install_action, dt_params.sort_order)(),
               '',
               getattr(InstallJob.scheduled_time, dt_params.sort_order)(),
               getattr(InstallJob.packages, dt_params.sort_order)(),
               getattr(InstallJob.created_by, dt_params.sort_order)(),
               '']

    install_jobs = query.order_by(columns[dt_params.column_order])\
        .filter(and_(InstallJob.status == None), or_(*clauses))\
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response.update(get_install_job_json_dict(install_jobs))

    return jsonify(**response)


@datatable.route('/api/get_in_progress_install_jobs/')
@login_required
def api_get_in_progress_install_jobs():
    dt_params = DataTableParams(request)
    db_session = DBSession()

    clauses = []
    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(Host.hostname.like(criteria))
        clauses.append(InstallJob.install_action.like(criteria))
        clauses.append(InstallJob.scheduled_time.like(criteria))
        clauses.append(InstallJob.start_time.like(criteria))
        clauses.append(InstallJob.packages.like(criteria))
        clauses.append(InstallJob.status.like(criteria))
        clauses.append(InstallJob.created_by.like(criteria))

    query = db_session.query(InstallJob)\
        .join(Host, Host.id == InstallJob.host_id)

    total_count = query.filter(and_(InstallJob.status != None, InstallJob.status != JobStatus.FAILED)).count()
    filtered_count = query.filter(and_(InstallJob.status != None, InstallJob.status != JobStatus.FAILED), or_(*clauses)).count()

    columns = [getattr(Host.hostname, dt_params.sort_order)(),
               getattr(InstallJob.install_action, dt_params.sort_order)(),
               getattr(InstallJob.scheduled_time, dt_params.sort_order)(),
               getattr(InstallJob.start_time, dt_params.sort_order)(),
               getattr(InstallJob.packages, dt_params.sort_order)(),
               getattr(InstallJob.status, dt_params.sort_order)(),
               '',
               getattr(InstallJob.created_by, dt_params.sort_order)()]

    install_jobs = query.order_by(columns[dt_params.column_order])\
        .filter(and_(InstallJob.status != None, InstallJob.status != JobStatus.FAILED), or_(*clauses))\
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response.update(get_install_job_json_dict(install_jobs))

    return jsonify(**response)


@datatable.route('/api/get_failed_install_jobs/')
@login_required
def api_get_failed_install_jobs():
    dt_params = DataTableParams(request)
    db_session = DBSession()

    clauses = []
    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(Host.hostname.like(criteria))
        clauses.append(InstallJob.install_action.like(criteria))
        clauses.append(InstallJob.scheduled_time.like(criteria))
        clauses.append(InstallJob.start_time.like(criteria))
        clauses.append(InstallJob.packages.like(criteria))
        clauses.append(InstallJob.status_time.like(criteria))
        clauses.append(InstallJob.created_by.like(criteria))

    query = db_session.query(InstallJob)\
        .join(Host, Host.id == InstallJob.host_id)

    total_count = query.filter(InstallJob.status == JobStatus.FAILED).count()
    filtered_count = query.filter(and_(InstallJob.status == JobStatus.FAILED), or_(*clauses)).count()

    columns = [getattr(Host.hostname, dt_params.sort_order)(),
               getattr(InstallJob.install_action, dt_params.sort_order)(),
               getattr(InstallJob.scheduled_time, dt_params.sort_order)(),
               getattr(InstallJob.start_time, dt_params.sort_order)(),
               getattr(InstallJob.packages, dt_params.sort_order)(),
               getattr(InstallJob.status_time, dt_params.sort_order)(),
               '',
               getattr(InstallJob.created_by, dt_params.sort_order)()]

    install_jobs = query.order_by(columns[dt_params.column_order])\
        .filter(and_(InstallJob.status == JobStatus.FAILED), or_(*clauses))\
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response.update(get_install_job_json_dict(install_jobs))

    return jsonify(**response)


@datatable.route('/api/get_completed_install_jobs/')
@login_required
def api_get_completed_install_jobs():
    dt_params = DataTableParams(request)
    db_session = DBSession()

    clauses = []
    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(Host.hostname.like(criteria))
        clauses.append(InstallJobHistory.install_action.like(criteria))
        clauses.append(InstallJobHistory.scheduled_time.like(criteria))
        clauses.append(InstallJobHistory.start_time.like(criteria))
        clauses.append(InstallJobHistory.packages.like(criteria))
        clauses.append(InstallJobHistory.status_time.like(criteria))
        clauses.append(InstallJobHistory.created_by.like(criteria))

    query = db_session.query(InstallJobHistory)\
        .join(Host, Host.id == InstallJobHistory.host_id)

    total_count = query.filter(InstallJobHistory.status == JobStatus.COMPLETED).count()
    filtered_count = query.filter(and_(InstallJobHistory.status == JobStatus.COMPLETED), or_(*clauses)).count()

    columns = [getattr(Host.hostname, dt_params.sort_order)(),
               getattr(InstallJobHistory.install_action, dt_params.sort_order)(),
               getattr(InstallJobHistory.scheduled_time, dt_params.sort_order)(),
               getattr(InstallJobHistory.start_time, dt_params.sort_order)(),
               getattr(InstallJobHistory.packages, dt_params.sort_order)(),
               getattr(InstallJobHistory.status_time, dt_params.sort_order)(),
               '',
               getattr(InstallJobHistory.created_by, dt_params.sort_order)()]

    install_jobs = query.order_by(columns[dt_params.column_order])\
        .filter(and_(InstallJobHistory.status == JobStatus.COMPLETED), or_(*clauses))\
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response.update(get_install_job_json_dict(install_jobs))

    return jsonify(**response)


@datatable.route('/api/hosts/<hostname>/install_job_history')
@login_required
def api_get_host_dashboard_install_job_history(hostname):
    dt_params = DataTableParams(request)
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if not host:
        abort(404)

    clauses = []
    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(Host.hostname.like(criteria))
        clauses.append(InstallJobHistory.install_action.like(criteria))
        clauses.append(InstallJobHistory.scheduled_time.like(criteria))
        clauses.append(InstallJobHistory.start_time.like(criteria))
        clauses.append(InstallJobHistory.packages.like(criteria))
        clauses.append(InstallJobHistory.status_time.like(criteria))
        clauses.append(InstallJobHistory.created_by.like(criteria))

    query = db_session.query(InstallJobHistory)\
        .join(Host, Host.id == InstallJobHistory.host_id)

    total_count = query.filter(InstallJobHistory.host_id == host.id).count()
    filtered_count = query.filter(and_(InstallJobHistory.host_id == host.id), or_(*clauses)).count()

    columns = [getattr(InstallJobHistory.install_action, dt_params.sort_order)(),
               getattr(InstallJobHistory.scheduled_time, dt_params.sort_order)(),
               getattr(InstallJobHistory.start_time, dt_params.sort_order)(),
               getattr(InstallJobHistory.packages, dt_params.sort_order)(),
               getattr(InstallJobHistory.status, dt_params.sort_order)(),
               getattr(InstallJobHistory.status_time, dt_params.sort_order)(),
               '',
               getattr(InstallJobHistory.created_by, dt_params.sort_order)()]

    install_jobs = query.order_by(columns[dt_params.column_order])\
        .filter(and_(InstallJobHistory.host_id == host.id), or_(*clauses))\
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response.update(get_install_job_json_dict(install_jobs))

    return jsonify(**response)


@datatable.route('/api/hosts/<hostname>/inventory')
@login_required
def api_get_inventory(hostname):
    rows = []
    dt_params = DataTableParams(request)
    db_session = DBSession()

    host = get_host(db_session, hostname)
    if not host:
        abort(404)

    clauses = []
    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(HostInventory.location.like(criteria))
        clauses.append(HostInventory.model_name.like(criteria))
        clauses.append(HostInventory.name.like(criteria))
        clauses.append(HostInventory.description.like(criteria))
        clauses.append(HostInventory.serial_number.like(criteria))
        clauses.append(HostInventory.hardware_revision.like(criteria))

    query = db_session.query(HostInventory)\
        .join(Host, Host.id == HostInventory.host_id)

    total_count = query.filter(HostInventory.host_id == host.id).count()
    filtered_count = query.filter(and_(HostInventory.host_id == host.id), or_(*clauses)).count()

    columns = [getattr(HostInventory.location, dt_params.sort_order)(),
               getattr(HostInventory.model_name, dt_params.sort_order)(),
               getattr(HostInventory.name, dt_params.sort_order)(),
               getattr(HostInventory.description, dt_params.sort_order)(),
               getattr(HostInventory.serial_number, dt_params.sort_order)(),
               getattr(HostInventory.hardware_revision, dt_params.sort_order)()]

    host_inventory = query.order_by(columns[dt_params.column_order])\
        .filter(and_(HostInventory.host_id == host.id), or_(*clauses))\
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    for inventory in host_inventory:
        row = dict()
        row['location'] = inventory.location
        row['model_name'] = inventory.model_name
        row['name'] = inventory.name
        row['description'] = inventory.description
        row['serial_number'] = inventory.serial_number
        row['vid'] = inventory.hardware_revision
        rows.append(row)

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response['data'] = rows

    return jsonify(**response)


@datatable.route('/api/search_inventory/')
@login_required
def api_search_inventory():
    request_args = request.args
    dt_params = DataTableParams(request)

    rows = []
    db_session = DBSession()

    search_filters = dict()

    search_filters['serial_number'] = request_args.get('serial_number')
    search_filters['region_ids'] = request_args.get('region_ids').split(',') \
        if request_args.get('region_ids') else []
    search_filters['chassis_types'] = request_args.get('chassis_types').split(',') \
        if request_args.get('chassis_types') else []
    search_filters['software_versions'] = request_args.get('software_versions').split(',') \
        if request_args.get('software_versions') else []
    search_filters['model_names'] = request_args.get('model_names').split(',') \
        if request_args.get('model_names') else []
    search_filters['partial_model_names'] = request_args.get('partial_model_names').split(',') \
        if request_args.get('partial_model_names') else []

    if request_args.get('available') == "true":
        results, total_count, filtered_count = handle_search_for_available_inventory(db_session,
                                                                                     search_filters, dt_params)
    else:
        results, total_count, filtered_count = handle_search_for_in_use_inventory(db_session,
                                                                                  search_filters, dt_params)

    for inventory_entry in results:
        row = {'model_name': inventory_entry.model_name,
               'serial_number': inventory_entry.serial_number,
               'description': inventory_entry.description}
        if hasattr(inventory_entry, 'notes'):
            row['notes'] = inventory_entry.notes
        else:
            row['hostname'] = ''
            row['region'] = ''
            row['chassis'] = ''
            row['platform'] = ''
            row['software'] = ''
            row['last_successful_retrieval'] = ''
            row['inventory_retrieval_status'] = ''
            row['name'] = inventory_entry.name

            host = inventory_entry.host
            if host:
                row['hostname'] = host.hostname
                row['chassis'] = host.platform
                row['platform'] = host.software_platform
                row['software'] = host.software_version
                row['region'] = host.region.name
                row['location'] = host.location

                inventory_job = host.inventory_job[0]
                if inventory_job and inventory_job.last_successful_time:
                    row['last_successful_retrieval'] = get_last_successful_inventory_elapsed_time(host)
                    row['inventory_retrieval_status'] = inventory_job.status

        rows.append(row)

    response = dict()
    response['draw'] = dt_params.draw
    response['recordsTotal'] = total_count
    response['recordsFiltered'] = filtered_count
    response['data'] = rows

    return jsonify(**response)


def handle_search_for_available_inventory(db_session, json_data, dt_params):

    results = query_available_inventory(db_session, json_data.get('serial_number'),
                                        json_data.get('model_names'), json_data.get('partial_model_names'))
    total_count = results.count()

    clauses = []

    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(Inventory.model_name.like(criteria))
        clauses.append(Inventory.serial_number.like(criteria))
        clauses.append(Inventory.description.like(criteria))
        clauses.append(Inventory.notes.like(criteria))

        results = results.filter(or_(*clauses))
        filtered_count = results.count()
    else:
        filtered_count = total_count

    columns = [getattr(Inventory.model_name, dt_params.sort_order)(),
               getattr(Inventory.serial_number, dt_params.sort_order)(),
               getattr(Inventory.description, dt_params.sort_order)(),
               getattr(Inventory.notes, dt_params.sort_order)()]

    results = results.order_by(columns[dt_params.column_order]) \
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length).all()

    return results, total_count, filtered_count


def handle_search_for_in_use_inventory(db_session, json_data, dt_params):

    results = query_in_use_inventory(db_session, json_data)
    total_count = results.count()

    clauses = []

    if len(dt_params.search_value):
        criteria = '%' + dt_params.search_value + '%'
        clauses.append(HostInventory.model_name.like(criteria))
        clauses.append(HostInventory.name.like(criteria))
        clauses.append(HostInventory.serial_number.like(criteria))
        clauses.append(HostInventory.description.like(criteria))

        clauses.append(Host.hostname.like(criteria))
        clauses.append(Host.platform.like(criteria))
        clauses.append(Host.software_platform.like(criteria))
        clauses.append(Host.software_version.like(criteria))
        clauses.append(Host.location.like(criteria))
        clauses.append(Region.name.like(criteria))

        results = results.join(Host, HostInventory.host_id == Host.id) \
            .join(Region, Host.region_id == Region.id) \
            .filter(or_(*clauses))
        filtered_count = results.count()
    else:
        filtered_count = total_count

    columns = [getattr(HostInventory.model_name, dt_params.sort_order)(),
               getattr(HostInventory.name, dt_params.sort_order)(),
               getattr(HostInventory.serial_number, dt_params.sort_order)(),
               getattr(HostInventory.description, dt_params.sort_order)(),
               getattr(Host.hostname, dt_params.sort_order)(),
               getattr(Host.platform, dt_params.sort_order)(),
               getattr(Host.software_platform, dt_params.sort_order)(),
               getattr(Host.software_version, dt_params.sort_order)(),
               getattr(Region.name, dt_params.sort_order)(),
               getattr(Host.location, dt_params.sort_order)()]

    results = results.order_by(columns[dt_params.column_order]) \
        .slice(dt_params.start_length, dt_params.start_length + dt_params.display_length)

    return results, total_count, filtered_count
