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
# ==============================================================================
from flask import jsonify
from flask import g

from common import get_jump_host_list
from common import get_jump_host
from common import create_or_update_jump_host
from common import delete_jump_host

from database import DBSession

from constants import ConnectionType

from utils import get_acceptable_string

from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import ENVELOPE
from api_utils import APIStatus
from api_utils import validate_url_parameters
from api_utils import convert_json_request_to_list
from api_utils import validate_required_keys_in_dict
from api_utils import validate_acceptable_keys_in_dict

from api_constants import HTTP_OK
from api_constants import HTTP_MULTI_STATUS_ERROR

# Acceptable JSON keys
KEY_HOSTNAME = 'hostname'
KEY_CONNECTION_TYPE = 'connection_type'
KEY_HOST_OR_IP = 'host_or_ip'
KEY_PORT_NUMBER = 'port_number'
KEY_USERNAME = 'username'
KEY_PASSWORD = 'password'


def api_create_jump_hosts(request):
    """
    POST:
    http://localhost:5000/api/v1/jump_hosts

    BODY:
    [{
      "hostname": "Jump_Host_1",
      "connection_type": "telnet",
      "host_or_ip": "1.1.1.1",
      "port_number": 5000,
      "username": "root",
      "password": "root"
    },{
      "hostname": "Jump_Host_2",
      "connection_type": "ssh",
      "host_or_ip": "my-server",
      "username": "root",
      "password": "root"

    }]
    """
    rows = []
    db_session = DBSession()
    error_found = False

    json_list = convert_json_request_to_list(request)

    for data in json_list:
        row = dict()
        try:
            validate_required_keys_in_dict(data, [KEY_HOSTNAME])

            hostname = get_acceptable_string(data[KEY_HOSTNAME])
            row[KEY_HOSTNAME] = hostname

            if len(hostname) == 0:
                raise ValueError("Jump host name '{}' is not valid.".format(data[KEY_HOSTNAME]))

            validate_acceptable_keys_in_dict(data, [KEY_HOSTNAME, KEY_CONNECTION_TYPE, KEY_HOST_OR_IP,
                                                    KEY_PORT_NUMBER, KEY_USERNAME, KEY_PASSWORD])

            jump_host = get_jump_host(db_session, hostname)
            if jump_host is None:
                # These are the required fields for a new jump host creation.
                validate_required_keys_in_dict(data, [KEY_CONNECTION_TYPE, KEY_HOST_OR_IP])

            connection_type = data.get(KEY_CONNECTION_TYPE)
            if connection_type is not None:
                if connection_type not in [ConnectionType.SSH, ConnectionType.TELNET]:
                    raise ValueError('Connection Type must be either telnet or ssh')
            else:
                connection_type = None if jump_host is None else jump_host.connection_type

            host_or_ip = data.get(KEY_HOST_OR_IP) if data.get(KEY_HOST_OR_IP) is not None else \
                (None if jump_host is None else jump_host.host_or_ip)

            port_number = data.get(KEY_PORT_NUMBER) if data.get(KEY_PORT_NUMBER) is not None else \
                (None if jump_host is None else jump_host.port_number)

            username = data.get(KEY_USERNAME) if data.get(KEY_USERNAME) is not None else \
                (None if jump_host is None else jump_host.username)

            password = data.get(KEY_PASSWORD) if data.get(KEY_PASSWORD) is not None else \
                (None if jump_host is None else jump_host.password)

            create_or_update_jump_host(db_session, hostname=hostname, connection_type=connection_type,
                                       host_or_ip=host_or_ip, port_number=port_number, username=username,
                                       password=password, created_by=g.api_user.username, jumphost=jump_host)

            row[STATUS] = APIStatus.SUCCESS

        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{ENVELOPE: {'jump_host_list': rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def api_get_jump_hosts(request):
    """
    GET:
    http://localhost:5000/api/v1/jump_hosts
    http://localhost:5000/api/v1/jump_hosts?hostname=Jump_Host_1
    """
    validate_url_parameters(request, [KEY_HOSTNAME])

    rows = []
    db_session = DBSession

    hostname = request.args.get(KEY_HOSTNAME)
    if hostname:
        jump_host = get_jump_host(db_session, hostname)
        if jump_host is None:
            raise ValueError("Jump host '{}' does not exist in the database.".format(hostname))

        jumphosts = [jump_host]
    else:
        jumphosts = get_jump_host_list(db_session)

    for jumphost in jumphosts:
        if jumphost is not None:
            row = dict()
            row[KEY_HOSTNAME] = jumphost.hostname
            row[KEY_CONNECTION_TYPE] = jumphost.connection_type
            row[KEY_HOST_OR_IP] = jumphost.host_or_ip
            row[KEY_PORT_NUMBER] = jumphost.port_number if jumphost.port_number else ''
            row[KEY_USERNAME] = jumphost.username if jumphost.username else ''
            rows.append(row)

    return jsonify(**{ENVELOPE: {'jump_host_list': rows}})


def api_delete_jump_host(hostname):
    db_session = DBSession()

    delete_jump_host(db_session, hostname)
    return jsonify(**{ENVELOPE: {KEY_HOSTNAME: hostname, STATUS: APIStatus.SUCCESS}})