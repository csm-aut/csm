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
import math

RECORDS_PER_PAGE = 1000
ENVELOPE = 'api_response'
STATUS = 'status'
STATUS_MESSAGE = 'status_message'

class APIStatus:
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


def get_total_pages(db_session, table, clauses):
    total_records = db_session.query(table).filter(and_(*clauses)).count()
    return int(math.ceil(float(total_records) / RECORDS_PER_PAGE))


def check_parameters(args, allowed_list):
    invalid_params = [arg for arg in args if arg not in allowed_list]

    if invalid_params:
        return False, jsonify(**{ENVELOPE: {STATUS: APIStatus.FAILED,
                                            STATUS_MESSAGE: 'Unrecognized parameter(s): {}'.format(','.join(invalid_params))}})
    return True, ''


def failed_response(message, return_code=400):
    return jsonify(**{ENVELOPE: {STATUS: APIStatus.FAILED, STATUS_MESSAGE: message}}), return_code
