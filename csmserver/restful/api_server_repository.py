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
from csm_exceptions.exceptions import ServerException

from common import get_server_list
from common import get_server
from common import create_or_update_server_repository
from common import delete_server_repository

from utils import get_acceptable_string

from database import DBSession

from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import APIStatus
from api_utils import check_parameters
from api_utils import failed_response


def api_create_server_repositories(request):
    '''
    [{
        "hostname": "Repository_1",
        "server_type": "TFTP",
        "tftp_server_path": "223.255.254.245",
        "home_directory": "/auto/tftp-sjc-users1"
    },{
        "hostname": "Repository_2",
        "server_type": "FTP",
        "server_address": "172.27.153.150",
        "home_directory": "/tftpboot"
    },{
        "hostname": "Repository_3",
        "server_type": "SFTP",
        "server_address": "nb-server3",
        "home_directory": " /auto/tftp-vista"
    }]
    '''
    rows = []
    db_session = DBSession()
    json_data = request.json
    # Server Repository information is expected to be an array of dictionaries
    if type(json_data) is not list:
        json_data = [json_data]

    return_code = 200
    partial_success = False

    uncommon_required_parameters = {
        'TFTP': ['tftp_server_path', 'file_directory'],
        'FTP': ['server_address', 'home_directory'],
        'SFTP': ['server_address', 'home_directory'],
        'LOCAL': ['device_path']
        #'SCP': ['remote_host', 'destination']
    }
    server_url = {
        'TFTP': 'tftp_server_path',
        'FTP': 'server_address',
        'SFTP': 'server_address',
        'LOCAL': 'device_path'
        #'SCP': 'remote_host'
    }
    server_directory = {
        'TFTP': 'file_directory',
        'FTP': 'home_directory',
        'SFTP': 'file_directory',
        'LOCAL': ''
        #'SCP': 'file_directory'
    }

    for data in json_data:
        row = {}
        status_message = None

        if 'hostname' not in data.keys():
                status_message = "Missing parameter 'hostname'."
        else:
            repo = get_server(db_session, data['hostname'])
            if repo is not None:
                row, success = api_edit_server_repositories(db_session, repo, data)
                if success:
                    partial_success = True
                else:
                    return_code = 400
            elif 'server_type' not in data.keys() or data['server_type'] not in uncommon_required_parameters.keys():
                status_message = 'Missing or invalid server_type. Accepted values are "TFTP", "FTP", "SFTP", "LOCAL", and "SCP".'

            else:
                for required_param in uncommon_required_parameters[data['server_type']]:
                    if required_param not in data.keys():
                        status_message = "Missing parameter '%s'." % required_param

        if status_message is None and row == {}:
            try:
                hostname = get_acceptable_string(data['hostname'])
                server_repository = create_or_update_server_repository(db_session,
                                       hostname=hostname,
                                       server_type=data['server_type'],
                                       server_url=data[server_url[data['server_type']]],
                                       username='' if 'username' not in data.keys() else data['username'],
                                       password='' if 'password' not in data.keys() else data['password'],
                                       vrf='' if 'vrf' not in data.keys() else data['vrf'],
                                       server_directory='' if data['server_type'] == "LOCAL" else data[server_directory[data['server_type']]],
                                       server=get_server(db_session, hostname))
                row[STATUS] = APIStatus.SUCCESS
                row['hostname'] = server_repository.hostname
                partial_success = True
            except Exception as e:
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = e.message
                row['hostname'] = data['hostname']
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

    return jsonify(**{'data': {'server_repository_list': rows}}), return_code


def api_edit_server_repositories(db_session, repo, data):
    row = {}

    server_urls = {
        'TFTP': 'tftp_server_path',
        'FTP': 'server_address',
        'SFTP': 'server_address',
        'LOCAL': 'device_path'
        #'SCP': 'scp_server_path'
    }
    server_directories = {
        'TFTP': 'file_directory',
        'FTP': 'home_directory',
        'SFTP': 'home_directory',
        'LOCAL': ''
        #'SCP': 'file_directory'
    }

    # server_type is not editable
    if 'server_type' in data.keys() and data['server_type'] != repo.server_type:
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = "Given server_type '%s' does not match database value '%s'; server_type cannot be edited." % \
                              (data['server_type'], repo.server_type)
        for key, value in data.iteritems():
            row[key] = value
        success = False
        return row, success

    server_type = repo.server_type
    server_url = repo.server_url if server_urls[server_type] not in data.keys() else data[server_urls[server_type]]
    server_directory = repo.server_directory if server_directories[server_type] not in data.keys() else data[server_directories[server_type]]

    try:
        repo = create_or_update_server_repository(db_session,
                                        hostname=repo.hostname,
                                        server_type=server_type,
                                        server_url=server_url,
                                        username=repo.username if 'username' not in data.keys()
                                            else data['username'],
                                        vrf=repo.vrf if 'vrf' not in data.keys()
                                            else data['vrf'],
                                        server_directory=server_directory,
                                        password=repo.server_type if 'password' not in data.keys()
                                            else data['password'],
                                        server=repo)
        row[STATUS] = APIStatus.SUCCESS
        row['hostname'] = repo.hostname
        success = APIStatus.SUCCESS
    except Exception as e:
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = e.message
        for key, value in data.iteritems():
            row[key] = value
        success = False

    return row, success


def api_get_server_repositories(request):
    params = {
        'TFTP': ['vrf'],
        'FTP': ['vrf', 'username'],
        'SFTP': ['username'],
        'LOCAL': []
        #'SCP': ['destination', 'username', 'password']
    }
    server_url = {
        'TFTP': 'tftp_server_path',
        'FTP': 'server_address',
        'SFTP': 'server_address',
        'LOCAL': 'device_path'
        #'SCP': 'remote_host'
    }
    server_directory = {
        'TFTP': 'file_directory',
        'FTP': 'home_directory',
        'SFTP': 'home_directory',
        'LOCAL': ''
        #'SCP': 'file_directory'
    }

    ok, response = check_parameters(request.args.keys(), ['hostname'])
    if not ok:
        return response, 400

    rows = []
    db_session = DBSession()

    hostname = request.args.get('hostname')
    if hostname:
        servers = [get_server(db_session, hostname)]
    else:
        servers = get_server_list(db_session)

    for server in servers:
        if server is not None:
            row = {}
            row['hostname'] = server.hostname
            row['sever_type'] = server.server_type
            for req in params[server.server_type]:
                row[req] = server.__getattribute__(req) if server.__getattribute__(req) is not None else ''
            row[server_url[server.server_type]] = server.server_url
            if server_directory[server.server_type] is not '':
                row[server_directory[server.server_type]] = server.server_directory
            rows.append(row)

    return jsonify(**{'data':{'server_repository_list': rows}})


def api_delete_server_repositories(hostname):
    db_session = DBSession()
    row = {}
    return_code = 200

    try:
        delete_server_repository(db_session, hostname)
        row['hostname'] = hostname
        row[STATUS] = APIStatus.SUCCESS
    except (ValueNotFound, ServerException) as e:
        row['hostname'] = hostname
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = e.message
        return_code = 400

    return jsonify(**{'data': {'server_repository_list': [row]}}), return_code