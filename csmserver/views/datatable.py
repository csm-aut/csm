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
from sqlalchemy import or_, and_

from flask.ext.login import login_required

from database import DBSession

from models import Host
from models import Region
from models import JumpHost
from models import ConnectionParam
from models import logger

from common import get_last_successful_inventory_elapsed_time

from constants import UNKNOWN
from utils import is_empty

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
            row = {}
            row['hostname'] = host.hostname
            row['region'] = '' if host.region is None else host.region.name

            if len(host.connection_param) > 0:
                row['host_or_ip'] = host.connection_param[0].host_or_ip
                row['chassis'] = host.platform
                row['platform'] = UNKNOWN if host.software_platform is None else host.software_platform
                row['software'] = UNKNOWN if host.software_version is None else host.software_version

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

    dictionary = {}
    dictionary['draw'] = dt_params.draw
    dictionary['recordsTotal'] = total_count
    dictionary['recordsFiltered'] = filtered_count
    dictionary['data'] = rows

    return jsonify(**dictionary)


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
            row = {}
            row['hostname'] = host.hostname
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

    dictionary = {}
    dictionary['draw'] = dt_params.draw
    dictionary['recordsTotal'] = total_count
    dictionary['recordsFiltered'] = filtered_count
    dictionary['data'] = rows

    return jsonify(**dictionary)
