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
from flask import render_template
from flask.ext.login import current_user
from flask.ext.login import login_required
from flask import request
from flask import jsonify, abort

from wtforms import Form, validators
from wtforms import TextAreaField
from wtforms import StringField
from wtforms import SelectField
from wtforms import IntegerField
from wtforms import PasswordField
from wtforms.validators import required

from database import DBSession

from constants import ConnectionType

from common import can_create
from common import fill_regions
from common import fill_software_profiles
from common import fill_jump_hosts
from common import get_region_by_id
from common import get_jump_host_by_id
from common import get_software_profile_by_id
from common import get_host
from common import create_or_update_host
from common import get_region_name_to_id_dict

from models import Region
from models import logger

from utils import is_empty
from utils import remove_extra_spaces
from utils import get_acceptable_string
from utils import generate_ip_range

import csv

host_import = Blueprint('host_import', __name__, url_prefix='/host_import')

HEADER_FIELD_HOSTNAME = 'hostname'
HEADER_FIELD_REGION = 'region'
HEADER_FIELD_LOCATION = 'location'
HEADER_FIELD_ROLES = 'roles'
HEADER_FIELD_IP = 'ip'
HEADER_FIELD_USERNAME = 'username'
HEADER_FIELD_PASSWORD = 'password'
HEADER_FIELD_CONNECTION = 'connection'
HEADER_FIELD_PORT = 'port'
HEADER_FIELD_ENABLE_PASSWORD = 'enable_password'

HEADER_FIELDS = [HEADER_FIELD_HOSTNAME, HEADER_FIELD_REGION, HEADER_FIELD_LOCATION,
                 HEADER_FIELD_ROLES, HEADER_FIELD_IP, HEADER_FIELD_USERNAME,
                 HEADER_FIELD_PASSWORD, HEADER_FIELD_CONNECTION, HEADER_FIELD_PORT,
                 HEADER_FIELD_ENABLE_PASSWORD]


@host_import.route('/')
@login_required
def import_hosts():
    if not can_create(current_user):
        abort(401)

    db_session = DBSession()

    form = HostImportForm(request.form)
    ip_range_dialog_form = IPRangeForm(request.form)

    fill_regions(db_session, form.region.choices)
    fill_jump_hosts(db_session, form.jump_host.choices)
    fill_software_profiles(db_session, form.software_profile.choices)

    return render_template('host/import_hosts.html', form=form,
                           ip_range_dialog_form=ip_range_dialog_form)


@host_import.route('/api/generate_ip_range', methods=['POST'])
@login_required
def api_generate_ip_range():
    data_list = request.form.get('data_list')
    input_data = {
        'beginIP':    request.form['beginIP'],
        'endIP':      request.form['endIP'],
        'step':       request.form.get('step'),
        'region':     request.form.get('region2'),
        'roles':      request.form.get('role'),
        'connection': request.form['connection'],
        'username':   request.form.get('username'),
        'password':   request.form.get('password'),
    }
    #input_data['region'] = get_region_by_id(DBSession(), input_data['region']).name
    input_data['step'] = int(input_data['step'])
    input_header = ['hostname', 'ip']

    for i in HEADER_FIELDS:
        if i in input_data.keys() and input_data[i]:
            input_header.append(i)

    if data_list:
        header = data_list.split('\n')[0].split(',')
    else:
        header = input_header

    is_valid = True
    for i in input_header:
        if i not in header:
            is_valid = False

    if not is_valid:
        return jsonify({'status': 'The current header line is not valid with the ip range input.'})
    elif not data_list:
        output = ','.join(header)
    else:
        output = ''

    # build the rest of the text after the header
    ips = generate_ip_range(input_data['beginIP'], input_data['endIP'])
    for ip in ips:
        if ips.index(ip) % input_data['step'] == 0:
            input_data['ip'] = ip
            input_data['hostname'] = ip
            line = []
            for column in header:
                if column in input_data.keys() and input_data[column]:
                    line.append(input_data[column])
                else:
                    line.append('')
            output += '\n' + ','.join(line)

    return jsonify({'status': 'OK', 'data_list': output})


def get_column_number(header, column_name):
    try:
        return header.index(column_name)
    except ValueError:
        return -1


def get_row_data(row_data, header, column_name):
    col = get_column_number(header, column_name)
    if col >= 0:
        return remove_extra_spaces(row_data[col].strip())
    return None


@host_import.route('/api/import_hosts', methods=['POST'])
@login_required
def api_import_hosts():
    region_id = int(request.form['region_id'])
    jump_host_id = int(request.form['jump_host_id'])
    software_profile_id = int(request.form['software_profile_id'])
    data_list = request.form['data_list']

    db_session = DBSession()

    if region_id == -1:
        return jsonify({'status': 'Region has not been specified.'})

    if region_id > 0:
        region = get_region_by_id(db_session, region_id)
        if region is None:
            return jsonify({'status': 'Region is no longer exists in the database.'})

    if jump_host_id > 0:
        jump_host = get_jump_host_by_id(db_session, jump_host_id)
        if jump_host is None:
            return jsonify({'status': 'Jump Host is no longer exists in the database.'})

    if software_profile_id > 0:
        software_profile = get_software_profile_by_id(db_session, software_profile_id)
        if software_profile is None:
            return jsonify({'status': 'Software Profile is no longer exists in the database.'})

    error = []
    reader = csv.reader(data_list.splitlines(), delimiter=',')
    header_row = next(reader)

    # header_row: ['hostname', 'location', 'roles', 'ip', 'username', 'password', 'connection', 'port']
    # Check mandatory data fields
    if HEADER_FIELD_HOSTNAME not in header_row:
        error.append('"hostname" is missing in the header.')

    if HEADER_FIELD_IP not in header_row:
        error.append('"ip" is missing in the header.')

    if HEADER_FIELD_CONNECTION not in header_row:
        error.append('"connection" is missing in the header.')

    for header_field in header_row:
        if header_field not in HEADER_FIELDS:
            error.append('"' + header_field + '" is not a correct header field.')

    if error:
        return jsonify({'status': '\n'.join(error)})

    error = []
    data_list = list(reader)

    region_dict = get_region_name_to_id_dict(db_session)

    # Check if each row has the same number of data fields as the header
    row = 2
    for row_data in data_list:
        if len(row_data) != len(header_row):
            error.append('line {} has wrong number of data fields - {}.'.format(row, row_data))
        else:
            hostname = get_acceptable_string(get_row_data(row_data, header_row, HEADER_FIELD_HOSTNAME))
            if is_empty(hostname):
                error.append('line {} has invalid hostname - {}.'.format(row, row_data))

            # Validate the connection type
            connection_type = get_row_data(row_data, header_row, HEADER_FIELD_CONNECTION)
            if is_empty(connection_type) or connection_type not in [ConnectionType.TELNET, ConnectionType.SSH]:
                error.append('line {} has a wrong connection type (should either be "telnet" or "ssh") - {}.'.format(row, row_data))

            region_name = get_acceptable_string(get_row_data(row_data, header_row, HEADER_FIELD_REGION))
            if region_name is not None:
                # No blank region is allowed
                if len(region_name) == 0:
                    error.append('line {} has no region specified - {}.'.format(row, row_data))
                else:
                    if region_name not in region_dict.keys():
                        # Create the new region
                        try:
                            region = Region(name=region_name, created_by=current_user.username)
                            db_session.add(region)
                            db_session.commit()

                            # Add to region dictionary for caching purpose.
                            region_dict[region_name] = region.id
                        except Exception as e:
                            logger.exception('api_import_hosts() hit exception')
                            error.append('Unable to create region {} - {}.'.format(region_name, e.message))
        row += 1

    if error:
        return jsonify({'status': '\n'.join(error)})

    # Import the data
    row = 2
    for row_data in data_list:
        try:
            created_by = current_user.username
            hostname = get_acceptable_string(get_row_data(row_data, header_row, HEADER_FIELD_HOSTNAME))

            # Check if the host already exists in the database.
            host = get_host(db_session, hostname)

            region_name = get_acceptable_string(get_row_data(row_data, header_row, HEADER_FIELD_REGION))
            if region_name is None:
                alternate_region_id = region_id
            else:
                alternate_region_id = region_dict[region_name]

            location = get_row_data(row_data, header_row, HEADER_FIELD_LOCATION)
            if host and location is None:
                location = host.location

            roles = get_row_data(row_data, header_row, HEADER_FIELD_ROLES)
            if host and roles is None:
                roles = host.roles

            host_or_ip = get_row_data(row_data, header_row, HEADER_FIELD_IP)
            if host and host_or_ip is None:
                host_or_ip = host.connection_param[0].host_or_ip

            connection_type = get_row_data(row_data, header_row, HEADER_FIELD_CONNECTION)
            if host and connection_type is None:
                connection_type = host.connection_param[0].connection_type

            username = get_row_data(row_data, header_row, HEADER_FIELD_USERNAME)
            if host and username is None:
                username = host.connection_param[0].username

            password = get_row_data(row_data, header_row, HEADER_FIELD_PASSWORD)
            if host and password is None:
                password = host.connection_param[0].password

            enable_password = get_row_data(row_data, header_row, HEADER_FIELD_ENABLE_PASSWORD)
            if host and enable_password is None:
                enable_password = host.connection_param[0].enable_password

            port_number = get_row_data(row_data, header_row, HEADER_FIELD_PORT)
            if host and port_number is None:
                port_number = host.connection_param[0].port_number

            # If no software profile is selected, retain the existing one instead of overwriting it.
            if host and (software_profile_id is None or software_profile_id <= 0):
                alternate_software_profile_id = host.software_profile_id
            else:
                alternate_software_profile_id = software_profile_id

            # If no jump host is selected, retain the existing one instead of overwriting it.
            if host and (jump_host_id is None or jump_host_id <= 0):
                alternate_jump_host_id = host.connection_param[0].jump_host_id
            else:
                alternate_jump_host_id = jump_host_id

            create_or_update_host(db_session, hostname, alternate_region_id, location, roles,
                                  alternate_software_profile_id, connection_type, host_or_ip,
                                  username, password, enable_password, port_number,
                                  alternate_jump_host_id, created_by, host)

        except Exception as e:
            return jsonify({'status': 'Line {} - {} - {}.'.format(row, e.message, row_data)})

        row += 1

    return jsonify({'status': 'OK'})


class HostImportForm(Form):
    region = SelectField('Region', coerce=int, choices=[(-1, '')])
    jump_host = SelectField('Jump Host', coerce=int, choices=[(-1, '')])
    software_profile = SelectField('Software Profile', coerce=int, choices=[(-1, '')])
    data_list = TextAreaField('')
    import_errors = TextAreaField('')


class IPRangeForm(Form):
    beginIP = StringField('Beginning IP', [required()])
    endIP = StringField('Ending IP', [required()])
    step = IntegerField('Step', [validators.NumberRange(min=1)])
    region2 = StringField('Region')
    role = StringField('Roles')
    connection_type = SelectField('Connection Type', coerce=str,
                                  choices=[(ConnectionType.TELNET, ConnectionType.TELNET),
                                           (ConnectionType.SSH, ConnectionType.SSH)])
    username = StringField('Username')
    password = PasswordField('Password')

