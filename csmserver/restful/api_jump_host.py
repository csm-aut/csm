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

from csm_exceptions.exceptions import ValueNotFound

from common import get_jump_host_list
from common import get_jump_host
from common import create_or_update_jump_host
from common import delete_jump_host

from database import DBSession

from utils import get_acceptable_string

from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import APIStatus
from api_utils import check_parameters
from api_utils import failed_response

def api_create_jump_hosts(request):
    '''
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
    '''
    rows = []
    db_session = DBSession()
    json_data = request.json
    # Jump Host information is expected to be an array of dictionaries
    if type(json_data) is not list:
        json_data = [json_data]

    return_code = 200
    partial_success = False

    for data in json_data:
        row = {}
        status_message = None

        if 'hostname' not in data.keys():
            status_message = 'Missing hostname.'
        else:
            jump_host = get_jump_host(db_session, data['hostname'])
            if jump_host is not None:
                row, success = api_edit_jump_host(db_session, jump_host, data)
                if success:
                    partial_success = True
                else:
                    return_code = 400
            elif 'connection_type' not in data.keys():
                status_message = 'Missing connection_type.'
            elif data['connection_type'] not in ['telnet', 'ssh']:
                status_message = "Invalid connection_type '%s'; acceptable values are 'ssh' and 'telnet'." \
                                % data['connection_type']
            elif 'host_or_ip' not in data.keys():
                status_message = "Missing host_or_ip."
            else:
                hostname = get_acceptable_string(data['hostname'])

        if status_message is None and row == {}:
            try:
                create_or_update_jump_host(db_session,
                                          hostname=hostname,
                                          connection_type=data['connection_type'],
                                          host_or_ip=data['host_or_ip'],
                                          port_number='' if 'port_number' not in data.keys() else data['port_number'],
                                          username='' if 'username' not in data.keys() else data['username'],
                                          password='' if 'password' not in data.keys() else data['password'],
                                          jumphost=get_jump_host(db_session, hostname))
                row[STATUS] = APIStatus.SUCCESS
                row['hostname'] = hostname
                partial_success = True
            except Exception as e:
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = e.message
                row['hostname'] = hostname
                return_code = 400
        elif row == {}:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = status_message
            for key, value in data.iteritems():
                row[key] = value
            return_code = 400

        rows.append(row)

    if return_code == 400 and partial_success:
        return_code = 207

    return jsonify(**{'data': {'jump_host_list': rows}}), return_code


def api_edit_jump_host(db_session, jump_host, data):
    row = {}

    if 'connection_type' in data.keys() and data['connection_type'] not in ['ssh', 'telnet']:
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = "Invalid connection_type '%s'; acceptable values are 'ssh' and 'telnet'." \
                                % data['connection_type']
        for key, value in data.iteritems():
            row[key] = value
        success = False
        return row, success

    try:
        create_or_update_jump_host(db_session,
                           hostname=jump_host.hostname,
                           connection_type=jump_host.connection_type if 'connection_type' not in data.keys()
                                else data['connection_type'],
                           host_or_ip=jump_host.host_or_ip if 'host_or_ip' not in data.keys()
                                else data['host_or_ip'],
                           port_number=jump_host.port_number if 'port_number' not in data.keys()
                                else data['port_number'],
                           username=jump_host.username if 'username' not in data.keys()
                                else data['username'],
                           password=jump_host.password if 'password' not in data.keys()
                                else data['password'],
                           jumphost=jump_host)
        row[STATUS] = APIStatus.SUCCESS
        row['hostname'] = jump_host.hostname
        success = True
    except Exception as e:
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = e.message
        row['hostname'] = data['hostname']
        success = False

    return row, success


def api_get_jump_hosts(request):
    '''
    GET:
    http://localhost:5000/api/v1/jump_hosts
    http://localhost:5000/api/v1/jump_hosts?hostname=Jump_Host_1
    '''
    ok, response = check_parameters(request.args.keys(), ['hostname'])
    if not ok:
        return response, 400

    rows = []
    db_session = DBSession

    hostname = request.args.get('hostname')
    if hostname:
        jumphosts = [get_jump_host(db_session, hostname)]
    else:
        jumphosts = get_jump_host_list(db_session)

    for jumphost in jumphosts:
        if jumphost is not None:
            row = {}
            row['hostname'] = jumphost.hostname
            row['connection_type'] = jumphost.connection_type
            row['host_or_ip'] = jumphost.host_or_ip
            row['port_number'] = jumphost.port_number if jumphost.port_number else ''
            row['username'] = jumphost.username if jumphost.username else ''
            rows.append(row)

    return jsonify(**{'data':{'jump_host_list': rows}})

def api_delete_jump_host(hostname):
    db_session = DBSession()
    row = {}
    return_code = 200

    try:
        delete_jump_host(db_session, hostname)
        row[STATUS] = APIStatus.SUCCESS
        row['hostname'] = hostname
    except ValueNotFound as e:
        #return failed_response(e.message)
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = e.message
        row['hostname'] = hostname
        return_code = 400

    return jsonify(**{'data':{'jump_host_list': [row]}}), return_code