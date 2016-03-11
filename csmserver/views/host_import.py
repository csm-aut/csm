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
from flask import jsonify, render_template, redirect, url_for
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
from wtforms.validators import Length, required

from constants import Platform
from constants import ConnectionType

from common import can_create
from common import fill_regions
from common import get_region
from common import get_region_by_id
from common import get_host

from models import InventoryJob
from models import Host
from models import ConnectionParam
from models import Region
from models import HostContext

from database import DBSession

from utils import remove_extra_spaces
from utils import get_acceptable_string
from utils import generate_ip_range

import csv

host_import = Blueprint('host_import', __name__, url_prefix='/host_import')

HEADER_FIELD_HOSTNAME = 'hostname'
HEADER_FIELD_REGION = 'region'
HEADER_FIELD_ROLES = 'roles'
HEADER_FIELD_IP = 'ip'
HEADER_FIELD_USERNAME = 'username'
HEADER_FIELD_PASSWORD = 'password'
HEADER_FIELD_CONNECTION = 'connection'
HEADER_FIELD_PORT = 'port'


@host_import.route('/')
@login_required
def import_hosts():
    if not can_create(current_user):
        abort(401)

    form = HostImportForm(request.form)
    fill_regions(form.region.choices)
    ip_range_dialog_form = IPRangeForm(request.form)
    #fill_regions(ip_range_dialog_form.region2.choices)

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
        'roles':       request.form.get('role'),
        'connection': request.form['connection'],
        'username':   request.form.get('username'),
        'password':   request.form.get('password'),
    }
    #input_data['region'] = get_region_by_id(DBSession(), input_data['region']).name
    input_data['step'] = int(input_data['step'])
    allowed_headers = ['hostname', 'region', 'roles', 'ip', 'username', 'password', 'connection', 'port']
    input_header = ['hostname', 'ip']

    for i in allowed_headers:
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
        output = (',').join(header)
    else:
        #output = data_list
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
            output += '\n' + (',').join(line)

    print output

    return jsonify({'status': 'OK', 'data_list': output})


def get_column_number(header, column_name):
    try:
        return header.index(column_name)
    except ValueError:
        return -1


@host_import.route('/api/import_hosts', methods=['POST'])
@login_required
def api_import_hosts():
    importable_header = [HEADER_FIELD_HOSTNAME, HEADER_FIELD_REGION, HEADER_FIELD_ROLES, HEADER_FIELD_IP,
                         HEADER_FIELD_USERNAME, HEADER_FIELD_PASSWORD, HEADER_FIELD_CONNECTION, HEADER_FIELD_PORT]
    region_id = request.form['region']
    data_list = request.form['data_list']

    db_session = DBSession()
    selected_region = get_region_by_id(db_session, region_id)
    if selected_region is None:
        return jsonify({'status': 'Region is no longer exists in the database.'})

    # Check mandatory data fields
    error = []
    reader = csv.reader(data_list.splitlines(), delimiter=',')
    header_row = next(reader)

    if HEADER_FIELD_HOSTNAME not in header_row:
        error.append('"hostname" is missing in the header.')

    if HEADER_FIELD_IP not in header_row:
        error.append('"ip" is missing in the header.')

    if HEADER_FIELD_CONNECTION not in header_row:
        error.append('"connection" is missing in the header.')

    for header_field in header_row:
        if header_field not in importable_header:
            error.append('"' + header_field + '" is not a correct header field.')

    if error:
        return jsonify({'status': ','.join(error)})

    # Check if each row has the same number of data fields as the header
    error = []
    data_list = list(reader)

    row = 2
    COLUMN_CONNECTION = get_column_number(header_row, HEADER_FIELD_CONNECTION)
    COLUMN_REGION = get_column_number(header_row, HEADER_FIELD_REGION)

    for row_data in data_list:
        if len(row_data) > 0:
            if len(row_data) != len(header_row):
                error.append('line %d has wrong number of data fields.' % row)
            else:
                if COLUMN_CONNECTION >= 0:
                    # Validate the connection type
                    data_field = row_data[COLUMN_CONNECTION]
                    if data_field != ConnectionType.TELNET and data_field != ConnectionType.SSH:
                        error.append('line %d has a wrong connection type (should either be "telnet" or "ssh").' % row)
                if COLUMN_REGION >= 0:
                    # Create a region if necessary
                    data_field = get_acceptable_string(row_data[COLUMN_REGION])
                    region = get_region(db_session, data_field)
                    if region is None and data_field:
                        try:
                            db_session.add(Region(name=data_field,
                                                  created_by=current_user.username))
                            db_session.commit()
                        except Exception:
                            db_session.rollback()
                            error.append('Unable to create region %s.' % data_field)

        row += 1

    if error:
        return jsonify({'status': ','.join(error)})

    # Import the data
    error = []
    im_regions = {}

    for data in data_list:
        if len(data) == 0:
            continue

        db_host = None
        im_host = Host()
        im_host.region_id = selected_region.id
        im_host.created_by = current_user.username
        im_host.inventory_job.append(InventoryJob())
        im_host.context.append(HostContext())
        im_host.connection_param.append(ConnectionParam())
        im_host.connection_param[0].username = ''
        im_host.connection_param[0].password = ''
        im_host.connection_param[0].port_number = ''

        for column in range(len(header_row)):

            header_field = header_row[column]
            data_field = data[column].strip()

            if header_field == HEADER_FIELD_HOSTNAME:
                hostname = get_acceptable_string(data_field)
                db_host = get_host(db_session, hostname)
                im_host.hostname = hostname
            elif header_field == HEADER_FIELD_REGION:
                region_name = get_acceptable_string(data_field)
                if region_name in im_regions:
                    im_host.region_id = im_regions[region_name]
                else:
                    region = get_region(db_session, region_name)
                    if region is not None:
                        im_host.region_id = region.id
                        # Saved for later lookup
                        im_regions[region_name] = region.id
            elif header_field == HEADER_FIELD_ROLES:
                im_host.roles = remove_extra_spaces(data_field)
            elif header_field == HEADER_FIELD_IP:
                im_host.connection_param[0].host_or_ip = remove_extra_spaces(data_field)
            elif header_field == HEADER_FIELD_USERNAME:
                username = get_acceptable_string(data_field)
                im_host.connection_param[0].username = username
            elif header_field == HEADER_FIELD_PASSWORD:
                im_host.connection_param[0].password = data_field
            elif header_field == HEADER_FIELD_CONNECTION:
                im_host.connection_param[0].connection_type = data_field
            elif header_field == HEADER_FIELD_PORT:
                im_host.connection_param[0].port_number = remove_extra_spaces(data_field)

        # Import host already exists in the database, just update it
        if db_host is not None:
            db_host.created_by = im_host.created_by
            db_host.region_id = im_host.region_id

            if HEADER_FIELD_ROLES in header_row:
                db_host.roles = im_host.roles

            if HEADER_FIELD_IP in header_row:
                db_host.connection_param[0].host_or_ip = im_host.connection_param[0].host_or_ip

            if HEADER_FIELD_USERNAME in header_row:
                db_host.connection_param[0].username = im_host.connection_param[0].username

            if HEADER_FIELD_PASSWORD in header_row:
                db_host.connection_param[0].password = im_host.connection_param[0].password

            if HEADER_FIELD_CONNECTION in header_row:
                db_host.connection_param[0].connection_type = im_host.connection_param[0].connection_type

            if HEADER_FIELD_PORT in header_row:
                db_host.connection_param[0].port_number = im_host.connection_param[0].port_number
        else:
            # Add the import host
            db_session.add(im_host)

    if error:
        return jsonify({'status': error})
    else:
        db_session.commit()
        return jsonify({'status': 'OK'})


class HostImportForm(Form):
    region = SelectField('Region', coerce=int, choices=[(-1, '')])
    data_list = TextAreaField('')

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

