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

from common import get_region
from common import get_region_list
from common import create_or_update_region
from common import delete_region

from database import DBSession

from api_constants import HTTP_OK
from api_constants import HTTP_MULTI_STATUS_ERROR

from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import ENVELOPE
from api_utils import APIStatus
from api_utils import validate_url_parameters
from api_utils import convert_json_request_to_list
from api_utils import validate_required_keys_in_dict
from api_utils import validate_acceptable_keys_in_dict
from api_utils import convert_value_to_list

from utils import get_acceptable_string

# Acceptable JSON keys
KEY_REGION_NAME = 'region_name'
KEY_SERVER_REPOSITORIES = 'server_repositories'


def api_create_regions(request):
    """
    POST:
    http://localhost:5000/api/v1/regions

    BODY:
    [{
      "name": "Region_1"
      "server_repository": ["Repository1", "Repository2"]

    },{
      "name": "Region_2"
    }]
    """
    rows = []
    db_session = DBSession()
    error_found = False

    json_list = convert_json_request_to_list(request)

    for data in json_list:
        row = dict()
        try:
            validate_required_keys_in_dict(data, [KEY_REGION_NAME])

            region_name = get_acceptable_string(data[KEY_REGION_NAME])
            row[KEY_REGION_NAME] = region_name

            if region_name is None or len(region_name) == 0:
                raise ValueError("'{}' is an invalid region name.".format(data[KEY_REGION_NAME]))

            validate_acceptable_keys_in_dict(data, [KEY_REGION_NAME, KEY_SERVER_REPOSITORIES])

            # If the server_repositories is not in the json, it will return None
            server_repositories = convert_value_to_list(data, KEY_SERVER_REPOSITORIES)

            region = get_region(db_session, region_name)
            if region is not None and server_repositories is None:
                server_repositories = get_region_server_name_list(region)

            create_or_update_region(db_session=db_session,
                                    region_name=region_name,
                                    server_repositories=None if server_repositories is None else ','.join(server_repositories),
                                    created_by=g.api_user.username,
                                    region=region)

            row[STATUS] = APIStatus.SUCCESS

        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{ENVELOPE: {'region_list': rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def get_region_server_name_list(region):
    server_name_list = []
    for server in region.servers:
        server_name_list.append(server.hostname)

    return server_name_list


def api_get_regions(request):
    """
    GET:
    http://localhost:5000/api/v1/regions
    http://localhost:5000/api/v1/regions?name=Region_1
    """
    validate_url_parameters(request, [KEY_REGION_NAME])

    rows = []
    db_session = DBSession

    region_name = request.args.get(KEY_REGION_NAME)
    if region_name:
        region = get_region(db_session, region_name)
        if region is None:
            raise ValueError("Region '{}' does not exist in the database.".format(region_name))

        regions = [region]
    else:
        regions = get_region_list(db_session)

    for region in regions:
        if region is not None:
            row = dict()
            row[KEY_REGION_NAME] = region.name
            row[KEY_SERVER_REPOSITORIES] = [s.hostname for s in region.servers]
            rows.append(row)

    return jsonify(**{ENVELOPE: {'region_list': rows}})


def api_delete_region(name):
    db_session = DBSession()

    delete_region(db_session, name)
    return jsonify(**{ENVELOPE: {KEY_REGION_NAME: name, STATUS: APIStatus.SUCCESS}})
