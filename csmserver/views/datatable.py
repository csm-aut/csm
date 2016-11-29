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
from models import ConnectionParam
from models import logger

from common import get_last_successful_inventory_elapsed_time

from constants import UNKNOWN

datatable = Blueprint('datatable', __name__, url_prefix='/datatable')


@datatable.route('/api/get_managed_hosts/region/<int:region_id>')
@login_required
def get_server_managed_hosts(region_id):
    search_value = request.args.get('search[value]')
    start_length = int(request.args.get('start'))
    display_length = int(request.args.get('length'))
    draw = int(request.args.get('draw'))
    sort_order = request.args.get('order[0][dir]')
    column_order = int(request.args.get('order[0][column]'))

    rows = []
    db_session = DBSession()

    clauses = []
    if len(search_value):
        criteria = '%' + search_value + '%'
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

    columns = [getattr(Host.hostname, sort_order)(),
               getattr(Region.name, sort_order)(),
               getattr(ConnectionParam.host_or_ip, sort_order)(),
               getattr(Host.platform, sort_order)(),
               getattr(Host.software_platform, sort_order)(),
               getattr(Host.software_version, sort_order)()]

    hosts = query.order_by(columns[column_order]).slice(start_length, start_length + display_length).all()

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
                    row['software'] = UNKNOWN

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
    dictionary['draw'] = draw
    dictionary['recordsTotal'] = total_count
    dictionary['recordsFiltered'] = filtered_count
    dictionary['data'] = rows

    return jsonify(**dictionary)
