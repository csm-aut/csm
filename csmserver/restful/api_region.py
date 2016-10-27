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
from csm_exceptions.exceptions import RegionException

from common import get_region
from common import get_region_list
from common import get_server
from common import create_or_update_region
from common import delete_region

from database import DBSession

from models import Host

from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import APIStatus
from api_utils import check_parameters
from api_utils import failed_response

def api_create_regions(request):
    '''
    POST:
    http://localhost:5000/api/v1/regions

    BODY:
    [{
      "name": "Region_1"
      "server_repository": "Repository1,Repository2"

    },{
      "name": "Region_2"
    }]
    '''
    rows = []
    db_session = DBSession()
    json_data = request.json
    # Region information is expected to be an array of dictionaries
    if type(json_data) is not list:
        json_data = [json_data]

    return_code = 200
    partial_success = False

    for data in json_data:
        row = {}
        status_message = None

        if 'name' not in data.keys():
            status_message = "Missing parameter 'name'."
        else:
            region = get_region(db_session, data['name'])
            if region is not None:
                row, success = api_edit_region(db_session, region, data)
                if success:
                    partial_success = True
                else:
                    return_code = 400
            else:
                if 'server_repositories' in data.keys():
                    for server in data['server_repositories'].split(','):
                        repo = get_server(db_session, server)
                        if not repo:
                            status_message = "Invalid value for server_repositories: %s" % server
                else:
                    data['server_repositories'] = ""

        if status_message is None and row == {}:
            try:
                region = create_or_update_region(db_session,
                             name=data['name'],
                             server_repositories=data['server_repositories'],
                             region=get_region(db_session, data['name']))
                row[STATUS] = APIStatus.SUCCESS
                row['name'] = region.name
                partial_success = True
            except Exception as e:
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = e.message
                row['name'] = data['name']
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

    return jsonify(**{'data': {'region_list': rows}}), return_code


def api_edit_region(db_session, region, data):
    row = {}

    try:
        region = create_or_update_region(db_session,
                             name=region.name if 'name' not in data.keys() else data['name'],
                             server_repositories=region.server_repositories if 'server_repositories' not in data.keys()
                                else data['server_repositories'],
                             region=region)
        row[STATUS] = APIStatus.SUCCESS
        row['name'] = region.name
        success = True
    except Exception as e:
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = e.message
        row['name'] = data['name']
        success = False

    return row, success


def api_get_regions(request):
    '''
    GET:
    http://localhost:5000/api/v1/regions
    http://localhost:5000/api/v1/regions?name=Region_1
    '''
    ok, response = check_parameters(request.args.keys(), ['name'])
    if not ok:
        return response, 400

    rows = []
    db_session = DBSession

    region_name = request.args.get('name')
    if region_name:
        regions = [get_region(db_session, region_name)]
    else:
        regions = get_region_list(db_session)

    for region in regions:
        if region is not None:
            row = {}
            row['name'] = region.name
            server_names = [s.hostname for s in region.servers]
            row['server_repositories'] = ",".join(server_names)
            rows.append(row)

    return jsonify(**{'data':{'region_list': rows}})


def api_delete_region(name):
    db_session = DBSession()
    row = {}
    return_code = 200

    try:
        delete_region(db_session, name)
        row['name'] = name
        row[STATUS] = APIStatus.SUCCESS
    except (ValueNotFound, RegionException) as e:
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = e.message
        row['name'] = name
        return_code = 400

    return jsonify(**{'data':{'region_list': [row]}}), return_code