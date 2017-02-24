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

from common import get_custom_command_profile
from common import get_custom_command_profile_list
from common import create_or_update_custom_command_profile
from common import delete_custom_command_profile

from database import DBSession

from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import ENVELOPE
from api_utils import APIStatus
from api_utils import validate_url_parameters
from api_utils import convert_json_request_to_list
from api_utils import validate_required_keys_in_dict
from api_utils import validate_acceptable_keys_in_dict
from api_utils import convert_value_to_list

from api_constants import HTTP_OK
from api_constants import HTTP_MULTI_STATUS_ERROR

from utils import is_empty
from utils import get_acceptable_string

# Acceptable JSON keys
KEY_PROFILE_NAME = 'profile_name'
KEY_COMMAND_LIST = 'command_list'


def api_create_custom_command_profiles(request):
    """
    POST:
    http://localhost:5000/api/v1/custom_command_profiles

    BODY:
    [{
      "profile_name": "Profile_1",
      "command_list": ["show inventory"]
    },{
      "profile_name": "Profile_2",
      "command_list": ["show platform"]
    }]
    """

    rows = []
    db_session = DBSession()
    error_found = False

    json_list = convert_json_request_to_list(request)

    for data in json_list:
        row = dict()
        try:
            validate_required_keys_in_dict(data, [KEY_PROFILE_NAME])

            profile_name = get_acceptable_string(data[KEY_PROFILE_NAME])
            row[KEY_PROFILE_NAME] = profile_name

            if profile_name is None or len(profile_name) == 0:
                raise ValueError("Invalid custom command profile name '{}'.".format(data[KEY_PROFILE_NAME]))

            validate_acceptable_keys_in_dict(data, [KEY_PROFILE_NAME, KEY_COMMAND_LIST])

            command_list = convert_value_to_list(data, KEY_COMMAND_LIST)
            command_list = None if command_list is None else ','.join(command_list)

            custom_command_profile = get_custom_command_profile(db_session, profile_name)
            if custom_command_profile is not None and command_list is None:
                command_list = custom_command_profile.command_list

            create_or_update_custom_command_profile(db_session=db_session,
                                                    profile_name=profile_name,
                                                    command_list=command_list,
                                                    created_by=g.api_user.username,
                                                    custom_command_profile=custom_command_profile)
            row[STATUS] = APIStatus.SUCCESS

        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{ENVELOPE: {'custom_command_profile_list': rows}}), \
                  (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def api_get_custom_command_profiles(request):
    """
    GET:
    http://localhost:5000/api/v1/custom_command_profiles
    http://localhost:5000/api/v1/custom_command_profiles?profile_name=Profile_1
    """
    validate_url_parameters(request, [KEY_PROFILE_NAME])

    rows = []
    db_session = DBSession

    profile_name = request.args.get(KEY_PROFILE_NAME)
    if profile_name:
        ccp = get_custom_command_profile(db_session, profile_name)
        if ccp is None:
            raise ValueError("Custom command profile '{}' does not exist in the database.".format(profile_name))

        ccps = [ccp]
    else:
        ccps = get_custom_command_profile_list(db_session)

    for ccp in ccps:
        if ccp is not None:
            row = dict()
            row[KEY_PROFILE_NAME] = ccp.profile_name
            row[KEY_COMMAND_LIST] = [] if is_empty(ccp.command_list) else ccp.command_list.split(',')
            row['created_by'] = ccp.created_by
            rows.append(row)

    return jsonify(**{ENVELOPE: {'custom_command_profile_list': rows}})


def api_delete_custom_command_profile(profile_name):
    db_session = DBSession()

    delete_custom_command_profile(db_session, profile_name)

    return jsonify(**{ENVELOPE: {KEY_PROFILE_NAME: profile_name, STATUS: APIStatus.SUCCESS}})
