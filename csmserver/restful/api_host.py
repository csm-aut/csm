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

from sqlalchemy import and_
from database import DBSession

from common import get_host
from common import create_or_update_host
from common import delete_host
from common import get_region
from common import get_region_list
from common import get_region_id_to_name_dict
from common import get_jump_host_id_to_name_dict
from common import get_software_profile_id_to_name_dict
from common import get_region_name_to_id_dict
from common import get_jump_host_name_to_id_dict
from common import get_software_profile_name_to_id_dict

from models import Host

from constants import ConnectionType

from utils import is_empty
from utils import get_acceptable_string

from api_utils import get_total_pages

from api_utils import validate_url_parameters
from api_utils import failed_response
from api_utils import check_none
from api_utils import convert_json_request_to_list
from api_utils import validate_required_keys_in_dict
from api_utils import convert_value_to_list
from api_utils import validate_acceptable_keys_in_dict

from api_constants import HTTP_OK
from api_constants import HTTP_MULTI_STATUS_ERROR
from api_constants import RECORDS_PER_PAGE
from api_constants import RESPONSE_ENVELOPE
from api_constants import RESPONSE_STATUS
from api_constants import RESPONSE_STATUS_MESSAGE
from api_constants import APIStatus

import json

# Acceptable JSON keys
KEY_HOSTNAME = 'hostname'
KEY_REGION = 'region'
KEY_LOCATION = 'location'
KEY_CONNECTION_TYPE = 'connection_type'
KEY_ROLES = 'roles'
KEY_TS_OR_IP = 'ts_or_ip'
KEY_PORT_NUMBER = 'port_number'
KEY_USERNAME = 'username'
KEY_PASSWORD = 'password'
KEY_ENABLE_PASSWORD = 'enable_password'
KEY_JUMP_HOST = 'jump_host'
KEY_SOFTWARE_PROFILE = 'software_profile'

KEY_FAMILY = 'family'
KEY_CHASSIS = 'chassis'
KEY_SOFTWARE_PLATFORM = 'software_platform'
KEY_SOFTWARE_VERSION = 'software_version'
KEY_OS_TYPE = 'os_type'
KEY_CREATED_BY = 'created_by'
KEY_CREATED_TIME = 'created_time'


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
           'password': 'cisco',
           'enable_password': 'cisco',
           'location': 'building 20'
           } ]

    RETURN:
        {"api_response": {
            "host_list": [ {"status": "SUCCESS", "hostname": "My Host 1"},
                           {"status": "SUCCESS", "hostname": "My Host 2"} ]

            }
        }
    """
    rows = []
    db_session = DBSession()
    error_found = False

    # Pre-fetched information to speed up bulk host creation.
    # region_dict = get_region_name_to_id_dict(db_session)
    jump_host_dict = get_jump_host_name_to_id_dict(db_session)
    software_profile_dict = get_software_profile_name_to_id_dict(db_session)

    json_list = convert_json_request_to_list(request)

    for data in json_list:
        row = dict()
        try:
            validate_required_keys_in_dict(data, [KEY_HOSTNAME])

            hostname = get_acceptable_string(data.get(KEY_HOSTNAME))
            row[KEY_HOSTNAME] = hostname

            if hostname is None or len(hostname) == 0:
                raise ValueError("'{}' is an invalid hostname.".format(data.get(KEY_HOSTNAME)))

            validate_acceptable_keys_in_dict(data, [KEY_HOSTNAME, KEY_REGION, KEY_LOCATION, KEY_ROLES,
                                                    KEY_SOFTWARE_PROFILE, KEY_CONNECTION_TYPE, KEY_TS_OR_IP,
                                                    KEY_PORT_NUMBER, KEY_USERNAME, KEY_PASSWORD,
                                                    KEY_ENABLE_PASSWORD, KEY_JUMP_HOST])

            host = get_host(db_session, hostname)
            if host is None:
                # These are the required fields for a new host creation.
                validate_required_keys_in_dict(data, [KEY_REGION, KEY_CONNECTION_TYPE, KEY_TS_OR_IP])

            region_name = data.get(KEY_REGION)
            # If region name is None, it is treated as an update to the existing host.
            if region_name is None and host is not None:
                region_id = host.region_id
            else:
                region = get_region(db_session, region_name)
                if region is None:
                    raise ValueError('Region "{}" does not exist in the database.'.format(region_name))

                region_id = region.id


            #value = get_id_from_value('Region', region_dict, data, KEY_REGION)
            #region_id = value if value is not None else \
            #    (None if host is None else host.region_id)

            value = get_id_from_value('Jump host', jump_host_dict, data, KEY_JUMP_HOST)
            jump_host_id = value if value is not None else \
                (None if host is None else host.connection_param[0].jump_host_id)

            value = get_id_from_value('Software profile', software_profile_dict, data, KEY_SOFTWARE_PROFILE)
            software_profile_id = value if value is not None else \
                (None if host is None else host.software_profile_id)

            connection_type = data.get(KEY_CONNECTION_TYPE)
            if connection_type is not None:
                if connection_type not in [ConnectionType.SSH, ConnectionType.TELNET]:
                    raise ValueError('Connection Type must be either telnet or ssh')
            else:
                connection_type = None if host is None else host.connection_param[0].connection_type

            roles = convert_value_to_list(data, KEY_ROLES)
            roles = ','.join(roles) if roles is not None else \
                (None if host is None else host.roles)

            host_or_ip = convert_value_to_list(data, KEY_TS_OR_IP)
            host_or_ip = ','.join(host_or_ip) if host_or_ip is not None else \
                (None if host is None else host.connection_param[0].host_or_ip)

            port_number = convert_value_to_list(data, KEY_PORT_NUMBER)
            port_number = ','.join(str(p) for p in port_number) if port_number is not None else \
                (None if host is None else host.connection_param[0].port_number)

            location = data.get(KEY_LOCATION) if data.get(KEY_LOCATION ) is not None else \
                (None if host is None else host.location)

            username = data.get(KEY_USERNAME) if data.get(KEY_USERNAME) is not None else \
                (None if host is None else host.connection_param[0].username)

            password = data.get(KEY_PASSWORD) if data.get(KEY_PASSWORD) is not None else \
                (None if host is None else host.connection_param[0].password)

            enable_password = data.get(KEY_ENABLE_PASSWORD) if data.get(KEY_ENABLE_PASSWORD) is not None else \
                (None if host is None else host.connection_param[0].enable_password)

            create_or_update_host(db_session=db_session, hostname=hostname, region_id=region_id,
                                  location=location, roles=roles,
                                  software_profile_id=software_profile_id,
                                  connection_type=connection_type,
                                  host_or_ip=host_or_ip, username=username,
                                  password=password, enable_password=enable_password,
                                  port_number=port_number, jump_host_id=jump_host_id,
                                  created_by=g.api_user.username, host=host)

            row[RESPONSE_STATUS] = APIStatus.SUCCESS

        except Exception as e:
            row[RESPONSE_STATUS] = APIStatus.FAILED
            row[RESPONSE_STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    # end loop

    return jsonify(**{RESPONSE_ENVELOPE: {'host_list': rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def get_id_from_value(item, dictionary, data, key):
    id = None
    name = data.get(key)
    if name:
        id = dictionary.get(name)
        if not id:
            raise ValueError('{} "{}" does not exist in the database.'.format(item, name))
    return id


def api_get_hosts(request):
    """
    GET:
    http://localhost:5000/api/v1/hosts
    http://localhost:5000/api/v1/hosts?hostname=Host_1
    http://localhost:5000/api/v1/hosts?region=SJ Labs
    http://localhost:5000/api/v1/hosts?region=SJ Labs&page=2
    http://localhost:5000/api/v1/hosts?region=SJ%20Labs&family=ASR9K
    """
    validate_url_parameters(request, [KEY_HOSTNAME, KEY_REGION, KEY_FAMILY, 'page'])

    page = 1
    clauses = []
    db_session = DBSession

    hostname = request.args.get(KEY_HOSTNAME)
    if hostname:
        host = get_host(db_session, hostname)
        if host is None:
            raise ValueError("Host '{}' does not exist in the database.".format(hostname))

        hosts = [host]
    else:
        try:
            page = int(request.args.get('page')) if request.args.get('page') else 1
            if page <= 0: page = 1
        except Exception:
            return failed_response('page must be an numeric value')

        region_name = request.args.get(KEY_REGION)
        if region_name:
            region = get_region(db_session, region_name)
            if region:
                clauses.append(Host.region_id == region.id)
            else:
                return failed_response("Region '{}' does not exist in the database.".format(region_name))

        family = request.args.get(KEY_FAMILY)
        if family:
            clauses.append(Host.family == family)

        hosts = get_hosts_by_page(db_session, clauses, page)

    region_dict = get_region_id_to_name_dict(db_session)
    jump_host_dict = get_jump_host_id_to_name_dict(db_session)
    software_profile_dict = get_software_profile_id_to_name_dict(db_session)

    rows = []
    for host in hosts:
        row = dict()
        row[KEY_HOSTNAME] = host.hostname
        row[KEY_REGION] = check_none(region_dict.get(host.region_id))
        row[KEY_ROLES] = [] if is_empty(host.roles) else host.roles.split(',')
        connection_param = check_none(host.connection_param[0])

        row[KEY_FAMILY] = check_none(host.family)
        row[KEY_CHASSIS] = check_none(host.platform)
        row[KEY_SOFTWARE_PLATFORM] = check_none(host.software_platform)
        row[KEY_SOFTWARE_VERSION] = check_none(host.software_version)
        row[KEY_OS_TYPE] = check_none(host.os_type)
        row[KEY_LOCATION] = check_none(host.location)
        row[KEY_SOFTWARE_PROFILE] = check_none(software_profile_dict.get(host.software_profile_id))
        row[KEY_CREATED_BY] = host.created_by
        row[KEY_CREATED_TIME] = host.created_time

        if connection_param:
            row[KEY_TS_OR_IP] = [] if is_empty(connection_param.host_or_ip) else connection_param.host_or_ip.split(',')
            row[KEY_CONNECTION_TYPE] = check_none(connection_param.connection_type)
            row[KEY_USERNAME] = check_none(connection_param.username)
            row[KEY_PORT_NUMBER] = [] if is_empty(connection_param.port_number) else connection_param.port_number.split(',')
            row[KEY_JUMP_HOST] = check_none(jump_host_dict.get(connection_param.jump_host_id))

        rows.append(row)

    total_pages = get_total_pages(db_session, Host, clauses)

    return jsonify(**{RESPONSE_ENVELOPE: {'host_list': rows}, 'current_page': page, 'total_pages': total_pages})


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
    db_session = DBSession()

    delete_host(db_session, hostname)
    return jsonify(**{RESPONSE_ENVELOPE: {KEY_HOSTNAME: hostname, RESPONSE_STATUS: APIStatus.SUCCESS}})


def get_hosts_by_page(db_session, clauses, page):
    return db_session.query(Host).filter(and_(*clauses)).\
        order_by(Host.hostname.asc()).slice((page - 1) * RECORDS_PER_PAGE, page * RECORDS_PER_PAGE).all()
