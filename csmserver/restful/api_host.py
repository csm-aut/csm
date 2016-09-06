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
from flask import jsonify
from flask import g
from flask.ext.login import current_user

from sqlalchemy import and_
from database import DBSession

from common import get_host
from common import create_or_update_host
from common import delete_host
from common import get_jump_host
from common import get_region
from common import get_region_by_id
from common import get_jump_host_by_id

from models import Host

from constants import UNKNOWN
from constants import ConnectionType

from utils import get_acceptable_string

from api_utils import get_total_pages
from api_utils import RECORDS_PER_PAGE
from api_utils import ENVELOPE
from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import APIStatus
from api_utils import check_parameters
from api_utils import failed_response

def api_create_hosts(request):
    """
    POST: http://localhost:5000/api/v1/hosts
    BODY:
        [ {'hostname': 'My Host 1',
           'region': 'SJ Labs',
           'roles': 'PE',
           'connection_type': 'telnet',
           'host_or_ip': '172.28.98.2',
           'username': 'cisco',
           'password': 'cisco'} ]

    RETURN:
        {"api_response": {
            "host_list": [ {"status": "SUCCESS", "hostname": "My Host 1"},
                           {"status": "SUCCESS", "hostname": "My Host 2"} ]

            }
        }
    """
    rows = []
    db_session = DBSession()

    if hasattr(current_user, 'username'):
        user = current_user.username
    else:
        user = g.api_user.username

    json_data = request.json
    # Host information is expected to be an array of dictionaries
    if type(json_data) is not list:
        json_data = [json_data]

    return_code = 200
    error_found = False
    try:
        for data in json_data:
            row = {}
            status_message = None
            try:
                hostname = get_acceptable_string(data.get('hostname'))
                row['hostname'] = hostname

                host = get_host(db_session, hostname)

                region = get_region(db_session, data.get('region'))
                if region is None:
                    status_message = 'Region %s does not exist' % data.get('region')
                else:
                    connection_type = data.get('connection_type')
                    if connection_type not in [ConnectionType.SSH, ConnectionType.TELNET]:
                        status_message = 'Connection Type must be either telnet or ssh'
                    else:
                        roles = data.get('roles')
                        host_or_ip = data.get('ts_or_ip')
                        username = data.get('username')
                        password = data.get('password')
                        enable_password = data.get('enable_password')
                        port_number = data.get('port_number')

                        jump_host_id = -1
                        if data.get('jump_host') is not None:
                            jump_host = get_jump_host(db_session, data.get('jump_host'))
                            if jump_host is None:
                                status_message = 'Jump Host %s does not exist' % data.get('jump_host')
                            jump_host_id = jump_host.id

                        if status_message is None:
                            create_or_update_host(db_session=db_session, hostname=hostname, region_id=region.id,
                                                  roles=roles, connection_type=connection_type,
                                                  host_or_ip=host_or_ip, username=username,
                                                  password=password, enable_password=enable_password, port_number=port_number,
                                                  jump_host_id=jump_host_id, created_by=user, host=host)

            except Exception as e:
                status_message = e.message
                db_session.rollback()

            if status_message is None:
                row[STATUS] = APIStatus.SUCCESS
            else:
                error_found = True
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = status_message

            rows.append(row)

    except Exception as e:
        return failed_response('Bad input parameters. ' + e.message)

    if error_found:
        return_code = 207

    return jsonify(**{ENVELOPE: {'host_list': rows}}), return_code


def api_get_hosts(request):
    """
    GET:
    http://localhost:5000/api/v1/hosts
    http://localhost:5000/api/v1/hosts?region=SJ Labs
    http://localhost:5000/api/v1/hosts?region=SJ Labs&page=2
    http://localhost:5000/api/v1/hosts?region=SJ%20Labs&family=ASR9K
    """
    ok, response = check_parameters(request.args.keys(), ['region', 'family', 'page'])
    if not ok:
        return response, 400

    rows = []
    db_session = DBSession
    try:
        page = int(request.args.get('page')) if request.args.get('page') else 1
        if page <= 0: page = 1
    except Exception:
        return failed_response('page must be an numeric value')

    clauses = []

    region_name = request.args.get('region')
    if region_name:
        region = get_region(db_session, region_name)
        if region:
            clauses.append(Host.region_id == region.id)
        else:
            return failed_response('Unknown region %s' % region_name)

    family = request.args.get('family')
    if family:
        clauses.append(Host.family == family)

    hosts = get_hosts_by_page(db_session, clauses, page)

    for host in hosts:
        row = {}
        row['hostname'] = host.hostname

        region = get_region_by_id(db_session, host.region_id)
        row['region'] = region.name if region else UNKNOWN

        row['roles'] = host.roles
        connection_param = host.connection_param[0]

        row['family'] = host.family
        row['hardware'] = host.platform
        row['software_platform'] = host.software_platform
        row['software_version'] = host.software_version
        row['os_type'] = host.os_type

        if connection_param:
            row['ts_or_ip'] = connection_param.host_or_ip
            row['connection_type'] = connection_param.connection_type
            row['host_username'] = connection_param.username
            row['port_number'] = connection_param.port_number

            jump_host = get_jump_host_by_id(db_session, connection_param.jump_host_id)
            row['jump_host'] = jump_host.hostname if jump_host else ""

        rows.append(row)

    total_pages = get_total_pages(db_session, Host, clauses)

    return jsonify(**{ENVELOPE: {'host_list': rows}, 'current_page': page, 'total_pages': total_pages})


def api_delete_host(hostname):
    """
    :param hostname:
    :return:
    {
        "api_response": {
            "status": "SUCCESS",
            "hostname": "My Host 2"
        }
    }
    or
    {
        "api_response": {
            "status": "FAILED",
            "hostname": "My Host 2",
            "status_message": "Unable to locate host My Host 2"
        }
    }
    """
    row = {}
    row['hostname'] = hostname

    db_session = DBSession()
    try:
        delete_host(db_session, hostname)
        row[STATUS] = APIStatus.SUCCESS
    except Exception as e:
        return failed_response(e.message)

    return jsonify(**{ENVELOPE: row})


def get_hosts_by_page(db_session, clauses, page):
    return db_session.query(Host).filter(and_(*clauses)).\
        order_by(Host.hostname.asc()).slice((page - 1) * RECORDS_PER_PAGE, page * RECORDS_PER_PAGE).all()
