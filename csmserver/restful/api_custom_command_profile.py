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

from common import get_custom_command_profile
from common import get_custom_command_profile_list
from common import create_or_update_custom_command_profile
from common import delete_custom_command_profile

from database import DBSession

from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import ENVELOPE
from api_utils import APIStatus
from api_utils import check_parameters
from api_utils import failed_response

def api_create_custom_command_profiles(request):
    '''
    POST:
    http://localhost:5000/api/v1/custom_command_profiles

    BODY:
    [{
      "profile_name": "Profile_1",
      "command_list": ""
    },{
      "profile_name": "Profile_2",
      "command_list": ""
    }]
    '''
    rows = []
    db_session = DBSession()
    json_data = request.json
    # Custom Command Profile information is expected to be an array of dictionaries
    if type(json_data) is not list:
        json_data = [json_data]

    return_code = 200
    partial_success = False

    for data in json_data:
        row = {}
        status_message = None

        if 'profile_name' not in data.keys():
            status_message = "Missing parameter 'profile_name'."
        else:
            ccp = get_custom_command_profile(db_session, data['profile_name'])
            if ccp is not None:
                row, success = api_edit_custom_command_profile(db_session, ccp, data)
                if success:
                    partial_success = True
                else:
                    return_code = 400

        if 'command_list' not in data.keys():
            status_message = "Missing parameter 'command_list'"

        if status_message is None and row == {}:
            try:
                ccp = create_or_update_custom_command_profile(db_session,
                                  profile_name=data['profile_name'],
                                  command_list=data['command_list'],
                                  custom_command_profile=get_custom_command_profile(db_session, data['profile_name']))
                row[STATUS] = APIStatus.SUCCESS
                row['profile_name'] = ccp.profile_name
                partial_success = True
            except Exception as e:
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = e.message
                row['profile_name'] = data['profile_name']
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

    return jsonify(**{ENVELOPE: {'custom_command_profile_list': rows}}), return_code



def api_edit_custom_command_profile(db_session, ccp, data):
    row = {}

    try:
        ccp = create_or_update_custom_command_profile(db_session,
                                         profile_name=ccp.profile_name if 'profile_name' not in data.keys() else data['profile_name'],
                                         command_list=ccp.command_list if 'command_list' not in data.keys() else data['command_list'],
                                         custom_command_profile=ccp)
        row[STATUS] = APIStatus.SUCCESS
        row['name'] = ccp.profile_name
        success = True
    except Exception as e:
        row[STATUS] = APIStatus.FAILED
        row[STATUS_MESSAGE] = e.message
        row['profile_name'] = data['profile_name']
        success = False

    return row, success


def api_get_custom_command_profiles(request):
    '''
    GET:
    http://localhost:5000/api/v1/custom_command_profiles
    http://localhost:5000/api/v1/custom_command_profiles?profile_name=Profile_1
    '''
    ok, response = check_parameters(request.args.keys(), ['profile_name'])
    if not ok:
        return response, 400

    rows = []
    db_session = DBSession

    profile_name = request.args.get('profile_name')
    if profile_name:
        ccps = [get_custom_command_profile(db_session, profile_name)]
    else:
        ccps = get_custom_command_profile_list(db_session)

    for ccp in ccps:
        if ccp is not None:
            row = {}
            row['profile_name'] = ccp.profile_name
            row['command_list'] = ccp.command_list
            row['created_by'] = ccp.created_by
            rows.append(row)

    return jsonify(**{ENVELOPE: {'custom_command_profile_list': rows}})


def api_delete_custom_command_profile(profile_name):
    db_session = DBSession()
    row = {}
    return_code = 200

    try:
        delete_custom_command_profile(db_session, profile_name)
        row[STATUS] = APIStatus.SUCCESS
        row['profile_name'] = profile_name
    except ValueNotFound as e:
        return failed_response(e.message)

    return jsonify(**{ENVELOPE: row}), return_code