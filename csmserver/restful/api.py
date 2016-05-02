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
from flask import Blueprint
from flask import jsonify
from flask import g
from flask import request
from flask.ext.httpauth import HTTPBasicAuth

from database import DBSession
from models import User
from api_utils import ENVELOPE
from common import can_create
from common import can_delete

import api_host
import api_cco

restful_api = Blueprint('restful', __name__, url_prefix='/api')
auth = HTTPBasicAuth()

"""
HTTP Return Codes:
    400 - Bad Request
    401 - Not Authorized
    404 - Not Found
"""
# --------------------------------------------------------------------------------------------------------------


@restful_api.route('/v1/token')
@auth.login_required
def get_auth_token():
    token = g.user.generate_auth_token(600)
    return jsonify({'token': token.decode('ascii')})


@auth.verify_password
def verify_password(username_or_token, password):
    """
    Called whenever @auth.login_required (HTTYBasicAuth) is invoked
    """
    # first authenticate with the token
    user = User.verify_auth_token(username_or_token)
    if not user:
        # Authenticate with username/password in the database
        db_session = DBSession()
        user, authenticated = User.authenticate(db_session.query, username_or_token, password)
        # If the user does not exist or the password failed authentication, return False
        if not user or not authenticated:
            return False

    g.user = user
    return True


@restful_api.route('/v1/hosts', methods=['GET', 'POST'])
@auth.login_required
def api_hosts():
    if request.method == 'POST':
        if not can_create(g.user):
            return jsonify(**{ENVELOPE: 'Not Authorized'}), 401
        return api_host.api_create_hosts(request)
    elif request.method == 'GET':
        return api_host.api_get_hosts(request)
    else:
        return jsonify(**{ENVELOPE: 'Bad request'}), 400

# --------------------------------------------------------------------------------------------------------------


@restful_api.route('/v1/hosts/<hostname>/delete', methods=['DELETE'])
@auth.login_required
def host_delete(hostname):
    if not can_delete(g.user):
        return jsonify(**{ENVELOPE: 'Not Authorized'}), 401
    return api_host.api_delete_host(hostname)


@restful_api.route('/v1/cco/catalog')
@auth.login_required
def get_cco_catalog():
    return api_cco.api_get_cco_catalog()


@restful_api.route('/v1/cco/software')
@auth.login_required
def get_cco_software():
    return api_cco.api_get_cco_software(request)


@restful_api.route('/v1/cco/software/<name_or_id>')
@auth.login_required
def get_cco_software_entry(name_or_id):
    return api_cco.api_get_cco_software_entry(request, name_or_id)

# --------------------------------------------------------------------------------------------------------------
