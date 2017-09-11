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

from database import DBSession

from common import get_user_list
from common import get_host_platform_and_version_summary_tuples

from api_constants import RESPONSE_ENVELOPE

KEY_USERNAME = 'username'
KEY_CREATED_TIME = 'created_time'
KEY_CREATED_MONTH = 'created_month'
KEY_CREATED_YEAR = 'created_year'
KEY_SOFTWARE_PLATFORM = 'software_platform'
KEY_SOFTWARE_VERSION = 'software_version'
KEY_COUNT = 'count'


def api_get_user_summary(request):
    """
    GET:
    http://localhost:5000/api/v1/executive_summary/get_user_summary
    """

    rows = []
    db_session = DBSession()

    users = get_user_list(db_session)

    for user in users:
        if user is not None:
            row = dict()
            row[KEY_USERNAME] = user.username
            row[KEY_CREATED_TIME] = user.created_time
            row[KEY_CREATED_MONTH] = user.created_time.month
            row[KEY_CREATED_YEAR] = user.created_time.year
            rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {'user_list': rows}})


def api_get_host_platform_and_version_summary(request):
    """
    GET:
    http://localhost:5000/api/v1/executive_summary/api_get_host_platform_and_version_summary
    """
    db_session = DBSession()
    result_tuples = get_host_platform_and_version_summary_tuples(db_session)

    rows = []
    for result_tuple in result_tuples:
        row = dict()
        row[KEY_SOFTWARE_PLATFORM] = result_tuple[0]
        row[KEY_SOFTWARE_VERSION] = result_tuple[1]
        row[KEY_COUNT] = result_tuple[2]
        rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {'host_list': rows}})
