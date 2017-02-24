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

from common import get_server_list
from common import get_server
from common import create_or_update_server_repository
from common import delete_server_repository

from utils import is_empty
from utils import get_acceptable_string

from database import DBSession

from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import ENVELOPE
from api_utils import APIStatus
from api_utils import validate_url_parameters
from api_utils import validate_required_keys_in_dict
from api_utils import convert_json_request_to_list
from api_utils import validate_acceptable_keys_in_dict

from api_constants import HTTP_OK
from api_constants import  HTTP_MULTI_STATUS_ERROR

from constants import ServerType

# Acceptable JSON keys
KEY_HOSTNAME = 'hostname'
KEY_SERVER_TYPE = 'server_type'
KEY_TFTP_SERVER_PATH = 'tftp_server_path'
KEY_SERVER_ADDRESS = 'server_address'
KEY_VRF = 'vrf'
KEY_FILE_DIRECTORY = 'file_directory'
KEY_HOME_DIRECTORY = 'home_directory'
KEY_USERNAME = 'username'
KEY_PASSWORD = 'password'
KEY_DEVICE_PATH = 'device_path'
KEY_DESTINATION_ON_HOST = 'destination_on_host'


params_dict = {
    ServerType.TFTP_SERVER: [KEY_VRF],
    ServerType.FTP_SERVER: [KEY_VRF, KEY_USERNAME],
    ServerType.SFTP_SERVER: [KEY_USERNAME],
    ServerType.LOCAL_SERVER: [],
    ServerType.SCP_SERVER: [KEY_USERNAME, KEY_DESTINATION_ON_HOST]
}
required_keys_dict = {
    ServerType.TFTP_SERVER: [KEY_TFTP_SERVER_PATH, KEY_FILE_DIRECTORY],
    ServerType.FTP_SERVER: [KEY_SERVER_ADDRESS, KEY_HOME_DIRECTORY],
    ServerType.SFTP_SERVER: [KEY_SERVER_ADDRESS, KEY_HOME_DIRECTORY],
    ServerType.LOCAL_SERVER: [KEY_DEVICE_PATH],
    ServerType.SCP_SERVER: [KEY_SERVER_ADDRESS, KEY_HOME_DIRECTORY, KEY_DESTINATION_ON_HOST]
}
acceptable_keys_dict = {
    ServerType.TFTP_SERVER: [KEY_HOSTNAME, KEY_SERVER_TYPE,
                             KEY_TFTP_SERVER_PATH, KEY_VRF, KEY_FILE_DIRECTORY],
    ServerType.FTP_SERVER: [KEY_HOSTNAME, KEY_SERVER_TYPE,
                            KEY_SERVER_ADDRESS, KEY_VRF, KEY_HOME_DIRECTORY,
                            KEY_USERNAME, KEY_PASSWORD],
    ServerType.SFTP_SERVER: [KEY_HOSTNAME, KEY_SERVER_TYPE, KEY_SERVER_ADDRESS,
                             KEY_HOME_DIRECTORY, KEY_USERNAME, KEY_PASSWORD],
    ServerType.LOCAL_SERVER: [KEY_HOSTNAME, KEY_SERVER_TYPE, KEY_DEVICE_PATH],
    ServerType.SCP_SERVER: [KEY_HOSTNAME, KEY_SERVER_TYPE, KEY_SERVER_ADDRESS, KEY_HOME_DIRECTORY,
                            KEY_USERNAME, KEY_PASSWORD, KEY_DESTINATION_ON_HOST]
}
server_url_dict = {
    ServerType.TFTP_SERVER: KEY_TFTP_SERVER_PATH,
    ServerType.FTP_SERVER: KEY_SERVER_ADDRESS,
    ServerType.SFTP_SERVER: KEY_SERVER_ADDRESS,
    ServerType.LOCAL_SERVER: KEY_DEVICE_PATH,
    ServerType.SCP_SERVER: KEY_SERVER_ADDRESS
}
server_directory_dict = {
    ServerType.TFTP_SERVER: KEY_FILE_DIRECTORY,
    ServerType.FTP_SERVER: KEY_HOME_DIRECTORY,
    ServerType.SFTP_SERVER: KEY_HOME_DIRECTORY,
    ServerType.LOCAL_SERVER: '',
    ServerType.SCP_SERVER: KEY_HOME_DIRECTORY
}


def api_create_server_repositories(request):
    """
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
        "home_directory": "/auto/tftp-vista"
    }]
    """
    rows = []
    db_session = DBSession()
    error_found = False

    json_list = convert_json_request_to_list(request)
    for data in json_list:
        row = dict()
        try:
            validate_required_keys_in_dict(data, [KEY_HOSTNAME, KEY_SERVER_TYPE])

            hostname = get_acceptable_string(data[KEY_HOSTNAME])
            row[KEY_HOSTNAME] = hostname

            if len(hostname) == 0:
                raise ValueError("Server repository name '{}' is not valid.".format(data[KEY_HOSTNAME]))

            server_type = data.get(KEY_SERVER_TYPE)
            if server_type not in [ServerType.TFTP_SERVER, ServerType.FTP_SERVER, ServerType.SFTP_SERVER,
                                   ServerType.LOCAL_SERVER, ServerType.SCP_SERVER]:
                raise ValueError("'{}' is not a supported server type.".format(server_type))

            row[KEY_SERVER_TYPE] = server_type

            validate_required_keys_in_dict(data, required_keys_dict[server_type])
            validate_acceptable_keys_in_dict(data, acceptable_keys_dict[server_type])

            server = get_server(db_session, hostname)
            if server is None:
                # These are the required fields for a new server repository creation.
                validate_required_keys_in_dict(data, required_keys_dict.get(server_type))

            server_url = data.get(server_url_dict[server_type])
            server_url = server_url if server_url is not None else \
                (None if server is None else server.server_url)

            server_directory = data.get(server_directory_dict[server_type])
            server_directory = server_directory if server_directory is not None else \
                (None if server is None else server.server_directory)

            vrf = data.get(KEY_VRF) if data.get(KEY_VRF) is not None else \
                (None if server is None else server.vrf)

            username = data.get(KEY_USERNAME) if data.get(KEY_USERNAME) is not None else \
                (None if server is None else server.username)

            password = data.get(KEY_PASSWORD) if data.get(KEY_PASSWORD) is not None else \
                (None if server is None else server.password)

            destination_on_host = data.get(KEY_DESTINATION_ON_HOST) if data.get(KEY_DESTINATION_ON_HOST) is not None else \
                (None if server is None else server.destination_on_host)

            create_or_update_server_repository(db_session,
                                               hostname=hostname,
                                               server_type=server_type,
                                               server_url=server_url,
                                               username=username,
                                               password=password,
                                               vrf=vrf,
                                               server_directory=server_directory,
                                               destination_on_host=destination_on_host,
                                               created_by=g.api_user.username,
                                               server=get_server(db_session, hostname))

            row[STATUS] = APIStatus.SUCCESS
        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{ENVELOPE: {'server_repository_list': rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def api_get_server_repositories(request):

    validate_url_parameters(request, [KEY_HOSTNAME])

    rows = []
    db_session = DBSession()

    hostname = request.args.get(KEY_HOSTNAME)
    if hostname:
        server = get_server(db_session, hostname)
        if server is None:
            raise ValueError("Server repository '{}' does not exist in the database.".format(hostname))

        servers = [server]
    else:
        servers = get_server_list(db_session)

    for server in servers:
        if server is not None:
            row = dict()
            row[KEY_HOSTNAME] = server.hostname
            row[KEY_SERVER_TYPE] = server.server_type

            for req in params_dict[server.server_type]:
                row[req] = server.__getattribute__(req) if server.__getattribute__(req) is not None else ''

            row[server_url_dict[server.server_type]] = server.server_url

            if not is_empty(server_directory_dict[server.server_type]):
                row[server_directory_dict[server.server_type]] = server.server_directory

            rows.append(row)

    return jsonify(**{ENVELOPE: {'server_repository_list': rows}})


def api_delete_server_repositories(hostname):
    db_session = DBSession()

    delete_server_repository(db_session, hostname)
    return jsonify(**{ENVELOPE: {KEY_HOSTNAME: hostname, STATUS: APIStatus.SUCCESS}})
