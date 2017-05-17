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

from common import can_create
from common import can_delete
from common import can_delete_install
from common import can_install

from api_utils import failed_response

from api_constants import HTTP_NOT_AUTHORIZED

import api_host
import api_cco
import api_install
import api_region
import api_jump_host
import api_server_repository
import api_custom_command_profile

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
    token = g.api_user.generate_auth_token(1800)
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

    g.api_user = user
    return True

# --------------------------------------------------------------------------------------------------------------


@restful_api.route('/v1/hosts', methods=['GET', 'POST'])
@auth.login_required
def api_hosts():
    try:
        DBSession().close()
        if request.method == 'POST':
            if not can_create(g.api_user):
                return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
            return api_host.api_create_hosts(request)
        elif request.method == 'GET':
            return api_host.api_get_hosts(request)
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/hosts/<hostname>/delete', methods=['DELETE'])
@auth.login_required
def host_delete(hostname):
    try:
        DBSession().close()
        if not can_delete(g.api_user):
            return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
        return api_host.api_delete_host(hostname)
    except Exception as e:
        return failed_response(e.message)

# --------------------------------------------------------------------------------------------------------------


@restful_api.route('/v1/regions', methods=['GET', 'POST'])
@auth.login_required
def api_regions():
    try:
        DBSession().close()
        if request.method == 'POST':
            if not can_create(g.api_user):
                return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
            return api_region.api_create_regions(request)
        elif request.method == 'GET':
            return api_region.api_get_regions(request)
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/regions/<name>/delete', methods=['DELETE'])
@auth.login_required
def region_delete(name):
    try:
        DBSession().close()
        if not can_delete(g.api_user):
            return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
        else:
            return api_region.api_delete_region(name)
    except Exception as e:
        return failed_response(e.message)

# --------------------------------------------------------------------------------------------------------------


@restful_api.route('/v1/jump_hosts', methods=['GET', 'POST'])
@auth.login_required
def api_jump_hosts():
    try:
        DBSession().close()
        if request.method == 'POST':
            if not can_create(g.api_user):
                return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
            return api_jump_host.api_create_jump_hosts(request)
        elif request.method == 'GET':
            return api_jump_host.api_get_jump_hosts(request)
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/jump_hosts/<hostname>/delete', methods=['DELETE'])
@auth.login_required
def jump_host_delete(hostname):
    try:
        DBSession().close()
        if not can_delete(g.api_user):
            return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
        return api_jump_host.api_delete_jump_host(hostname)
    except Exception as e:
        return failed_response(e.message)

# --------------------------------------------------------------------------------------------------------------


@restful_api.route('/v1/server_repositories', methods=['GET', 'POST'])
@auth.login_required
def api_server_repositories():
    try:
        DBSession().close()
        if request.method == 'POST':
            if not can_create(g.api_user):
                return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
            return api_server_repository.api_create_server_repositories(request)
        elif request.method == 'GET':
            return api_server_repository.api_get_server_repositories(request)
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/server_repositories/<hostname>/delete', methods=['DELETE'])
@auth.login_required
def server_repository_delete(hostname):
    try:
        DBSession().close()
        if not can_delete(g.api_user):
            return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
        else:
            return api_server_repository.api_delete_server_repositories(hostname)
    except Exception as e:
        return failed_response(e.message)


# --------------------------------------------------------------------------------------------------------------


@restful_api.route('/v1/cco/catalog')
@auth.login_required
def get_cco_catalog():
    try:
        DBSession().close()
        return api_cco.api_get_cco_catalog()
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/cco/software')
@auth.login_required
def get_cco_software():
    try:
        DBSession().close()
        return api_cco.api_get_cco_software(request)
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/cco/software/<name_or_id>')
@auth.login_required
def get_cco_software_entry(name_or_id):
    try:
        DBSession().close()
        return api_cco.api_get_cco_software_entry(request, name_or_id)
    except Exception as e:
        return failed_response(e.message)

# --------------------------------------------------------------------------------------------------------------


@restful_api.route('/v1/install', methods=['POST', 'GET'])
@auth.login_required
def create_install_job():
    try:
        DBSession().close()
        if request.method == 'POST':
            if not can_install(g.api_user):
                return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
            return api_install.api_create_install_request(request)
        elif request.method == 'GET':
            return api_install.api_get_install_request(request)
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/install/delete', methods=['DELETE'])
@auth.login_required
def install_job_delete():
    try:
        DBSession().close()
        if not can_delete_install(g.api_user):
            return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
        return api_install.api_delete_install_job(request)
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/install/logs/<int:id>')
@auth.login_required
def get_session_log(id):
    try:
        DBSession().close()
        if not can_install(g.api_user):
            return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
        return api_install.api_get_session_log(id)
    except Exception as e:
        return failed_response(e.message)

# -------------------------- ------------------------------------------------------------------------------------


@restful_api.route('/v1/custom_command_profiles', methods=['GET', 'POST'])
@auth.login_required
def api_custom_command_profiles():
    try:
        DBSession().close()
        if request.method == 'POST':
            if not can_create(g.api_user):
                return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)
            return api_custom_command_profile.api_create_custom_command_profiles(request)
        elif request.method == 'GET':
            return api_custom_command_profile.api_get_custom_command_profiles(request)
    except Exception as e:
        return failed_response(e.message)


@restful_api.route('/v1/custom_command_profiles/<profile_name>/delete', methods=['DELETE'])
@auth.login_required
def custom_command_profile_delete(profile_name):
    try:
        DBSession().close()
        if not can_delete(g.api_user):
            return failed_response('Not Authorized', return_code=HTTP_NOT_AUTHORIZED)

        return api_custom_command_profile.api_delete_custom_command_profile(profile_name)
    except Exception as e:
        return failed_response(e.message)

# --------------------------------------------------------------------------------------------------------------
