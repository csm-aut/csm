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
from sqlalchemy import and_

from flask import jsonify
from werkzeug.exceptions import BadRequest

from api_constants import HTTP_BAD_REQUEST
from api_constants import RECORDS_PER_PAGE
from api_constants import RESPONSE_STATUS
from api_constants import RESPONSE_STATUS_MESSAGE
from api_constants import RESPONSE_ENVELOPE
from api_constants import APIStatus

from constants import get_temp_directory

import os
import datetime
import math

def get_total_pages(db_session, table, clauses):
    total_records = db_session.query(table).filter(and_(*clauses)).count()
    return int(math.ceil(float(total_records) / RECORDS_PER_PAGE))


def convert_json_request_to_list(request):
    """
    Given a request instance, check the return json data to ensure it is a list of json blocks.
    If not, converts the data to a list.  If there is an error, raise an exception.
    :param request: A request instance.
    :return: Returns an array of individual json blocks.
    """
    try:
        json_data = request.json if type(request.json) is list else [request.json]
    except BadRequest:
        raise ValueError("Data in the HTTP Request is an invalid JSON.")

    return json_data


def convert_value_to_list(dictionary, key):
    """
    Given a dictionary and a key, make sure the key value is a list type.
    If the key does not exist in the dictionary, just return None.
    :param dictionary: A dictionary instance.
    :param key: A dictionary key.
    :return: Return a list type.
    """
    try:
        value = dictionary.get(key)
        return None if value is None else value if type(value) is list else [value]
    except:
        raise ValueError("The value associated with '{}' is expected to be a list type - {}.".format(key, dictionary))


def validate_acceptable_keys_in_dict(dictionary, key_list):
    result = []
    for key in dictionary.keys():
        if key not in key_list:
            result.append(key)

    if result:
        if len(result) == 1:
            raise ValueError("The following key, '{}', is invalid.".format(','.join(result)))
        else:
            raise ValueError("The following keys, '{}', are invalid.".format(','.join(result)))


def validate_required_keys_in_dict(dictionary, key_list):
    """
    Check if the dictionary contains the required keys.  If not, raise an exception.
    :param args: A request instance.
    :param key_list: The keys that should be in the json structure (only 1st level keys).
    :return: Returns an array of individual json blocks.
    """
    for key in key_list:
        if key not in dictionary.keys():
            raise ValueError("Missing JSON key: '{}'.".format(key))

    return dictionary


def validate_url_parameters(request, parameter_list):
    """
    Check if the url parameters in the request are in the parameter_list .  If not, raise an exception.
    :param args: A request instance.
    :param parameter_list: A list of parameters that are allowed in the URL request.
    """
    args = request.args.keys()

    invalid_params = [arg for arg in args if arg not in parameter_list]
    if invalid_params:
        if len(invalid_params) == 1:
            raise ValueError("Following parameter, '{}', is not allowed.".format(','.join(invalid_params)))
        else:
            raise ValueError("Following parameters, '{}', are not allowed.".format(','.join(invalid_params)))


def failed_response(message, return_code=HTTP_BAD_REQUEST):
    return jsonify(**{RESPONSE_ENVELOPE: {RESPONSE_STATUS: APIStatus.FAILED, RESPONSE_STATUS_MESSAGE: message}}), return_code


def check_none(s):
    return s if s else ""


def write_log(data, prefix='robot'):
    date_string = datetime.datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S_%f")

    output_file_path = os.path.join(get_temp_directory(), '{}_{}'.format(prefix, str(date_string)))

    with open(output_file_path, 'w') as fd:
        fd.write(data)
