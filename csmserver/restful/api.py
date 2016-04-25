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
from smu_info_loader import SMUInfoLoader
from api_utils import ENVELOPE
from common import can_create
from common import can_delete

import api_host
import datetime

restful_api = Blueprint('restful', __name__, url_prefix='/api')
auth = HTTPBasicAuth()


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


@restful_api.route('/v1/hosts/<hostname>/delete', methods=['DELETE'])
@auth.login_required
def host_delete(hostname):
    if not can_delete(g.user):
        return jsonify(**{ENVELOPE: 'Not Authorized'}), 401
    return api_host.api_delete_host(hostname)


@restful_api.route('/get_software_catalog')
@auth.login_required
def get_software_catalog():
    return jsonify(**{'data': SMUInfoLoader.get_catalog()})


@restful_api.route('/get_optimal_smus_since/platform/<platform>/release/<release>')
@auth.login_required
def get_optimal_smus_since(platform, release):
    date = request.args.get('date')
    date = datetime.datetime.strptime(date, "%m-%d-%Y")

    try:
        smu_loader = SMUInfoLoader(platform, release)
    except:
        return('Page does not exist; check platform and release', 404)

    rows = []
    for smu_info in smu_loader.get_optimal_smu_list():
        if datetime.datetime.strptime(smu_info.posted_date.split()[0], "%m/%d/%Y") >= date:
            rows = rows + get_smu_info(smu_info.id, platform, release)

    # Get the posted_date of each dictionary, split it at the first space so you get mm/dd/yyyy.
    # Convert that string to a datetime, then sort the list of dictionaries by the posted_dates.
    rows.sort(key=lambda k: datetime.datetime.strptime(k['posted_date'].split()[0], '%m/%d/%Y'), reverse=True)

    return jsonify(**{'data': rows})


@restful_api.route('/get_smus_since/platform/<platform>/release/<release>')
@auth.login_required
def get_smus_since(platform, release):
    date = request.args.get('date')
    date = datetime.datetime.strptime(date, "%m-%d-%Y")

    try:
        smu_loader = SMUInfoLoader(platform, release)
    except:
        return('Page does not exist; check platform and release', 404)

    rows = []
    for smu_info in smu_loader.get_smu_list():
        if datetime.datetime.strptime(smu_info.posted_date.split()[0], "%m/%d/%Y") >= date:
            rows = rows + get_smu_info(smu_info.id, platform, release)

    # Get the posted_date of each dictionary, split it at the first space so you get mm/dd/yyyy.
    # Convert that string to a datetime, then sort the list of dictionaries by the posted_dates.
    rows.sort(key=lambda k: datetime.datetime.strptime(k['posted_date'].split()[0], '%m/%d/%Y'), reverse=True)

    return jsonify(**{'data': rows})


@restful_api.route('/get_smu_details/platform/<platform>/release/<release>/smu_name/<smu_name>')
@auth.login_required
def api_get_smu_info_by_name(platform, release, smu_name):
    try:
        smu_loader = SMUInfoLoader(platform, release)
        smu_info = smu_loader.get_smu_info(smu_name)
    except:
        return('Page does not exist; check platform and release', 404)

    if smu_info is not None:
        return jsonify(**{'data': get_smu_info(smu_info.id, platform, release)})
    else:
        return('Page does not exist; check smu_name', 404)


@restful_api.route('/get_smu_details/platform/<platform>/release/<release>/smu_id/<smu_id>')
@auth.login_required
def api_get_smu_info_by_id(platform, release, smu_id):
    try:
        SMUInfoLoader(platform, release)
    except:
        return('Page does not exist; check platform and release', 404)

    data = get_smu_info(smu_id, platform, release)
    if data:
        return jsonify(**{'data': data})
    else:
        return('Page does not exist; check smu_id', 404)


def get_smu_info(smu_id, platform, release):
    rows = []
    smu_loader = SMUInfoLoader(platform, release)
    smu_info = smu_loader.get_smu_info_by_id(smu_id)
    if smu_info is not None:
        row = {}
        row['id'] = smu_info.id
        row['name'] = smu_info.name
        row['status'] = smu_info.status
        row['type'] = smu_info.type
        row['posted_date'] = smu_info.posted_date
        row['ddts'] = smu_info.ddts
        row['description'] = smu_info.description
        row['functional_areas'] = smu_info.functional_areas
        row['impact'] = smu_info.impact
        row['package_bundles'] = smu_info.package_bundles
        row['compressed_image_size'] = str(smu_info.compressed_image_size)
        row['uncompressed_image_size'] = str(smu_info.uncompressed_image_size)
        row['prerequisites'] = smu_info.prerequisites
        row['supersedes'] = smu_info.supersedes
        row['superseded_by'] = smu_info.superseded_by
        row['composite_DDTS'] = smu_info.composite_DDTS
        row['prerequisites_smu_ids'] = ""
        row['supersedes_smu_ids'] = ""
        row['superseded_by_smu_ids'] = ""

        if smu_info.prerequisites != "":
            prereqs = smu_info.prerequisites.split(',')
            for smu in prereqs:
                prereq = smu_loader.get_smu_info(smu)
                row['prerequisites_smu_ids'] = row['prerequisites_smu_ids'] + prereq.id + ','
            row['prerequisites_smu_ids'] = row['prerequisites_smu_ids'][:-1]

        if smu_info.supersedes != "":
            supersedes = smu_info.supersedes.split(',')
            for smu in supersedes:
                supersedes_info = smu_loader.get_smu_info(smu)
                row['supersedes_smu_ids'] = row['supersedes_smu_ids'] + supersedes_info.id + ','
            row['supersedes_smu_ids'] = row['supersedes_smu_ids'][:-1]

        if smu_info.superseded_by != "":
            superseded_by = smu_info.superseded_by.split(',')
            for smu in superseded_by:
                supersedes_info = smu_loader.get_smu_info(smu)
                row['superseded_by_smu_ids'] = row['superseded_by_smu_ids'] + supersedes_info.id + ','
            row['superseded_by_smu_ids'] = row['superseded_by_smu_ids'][:-1]

        rows.append(row)

    return rows