from flask import Blueprint
from flask import jsonify, render_template, redirect, url_for
from flask.ext.login import current_user
from flask.ext.login import login_required
from flask import request
from flask import jsonify, abort

from wtforms import Form
from wtforms import TextAreaField
from wtforms import StringField
from wtforms import SelectField

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

from database import DBSession

from utils import remove_extra_spaces

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

@host_import.route('/', methods=['GET', 'POST'])
@login_required
def import_hosts():
    if not can_create(current_user):
        abort(401)

    form = HostImportForm(request.form)
    fill_regions(form.region.choices)

    if request.method == 'POST' and form.validate():
        return redirect(url_for('home'))

    return render_template('host/import_hosts.html', form=form)

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
    platform = request.form['platform']
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
                    # Validat the connection type
                    data_field = row_data[COLUMN_CONNECTION]
                    if data_field != ConnectionType.TELNET and data_field != ConnectionType.SSH:
                        error.append('line %d has a wrong connection type (should either be "telnet" or "ssh").' % row)
                if COLUMN_REGION >= 0:
                    # Create a region if necessary
                    data_field = row_data[COLUMN_REGION]
                    region = get_region(db_session, data_field)
                    if region is None:
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
        im_host.platform = platform
        im_host.region_id = selected_region.id
        im_host.created_by = current_user.username
        im_host.inventory_job.append(InventoryJob())
        im_host.connection_param.append(ConnectionParam())
        im_host.connection_param[0].username = ''
        im_host.connection_param[0].password = ''

        for column in range(len(header_row)):

            header_field = header_row[column]
            data_field = data[column]

            if header_field == HEADER_FIELD_HOSTNAME:
                db_host = get_host(db_session, data_field)
                im_host.hostname = data_field
            elif header_field == HEADER_FIELD_REGION:
                if data_field in im_regions:
                    im_host.region_id = im_regions[data_field]
                else:
                    region = get_region(db_session, data_field)
                    if region is not None:
                        im_host.region_id = region.id
                        # Saved for later lookup
                        im_regions[data_field] = region.id
            elif header_field == HEADER_FIELD_ROLES:
                im_host.roles = remove_extra_spaces(data_field)
            elif header_field == HEADER_FIELD_IP:
                im_host.connection_param[0].host_or_ip = remove_extra_spaces(data_field)
            elif header_field == HEADER_FIELD_USERNAME:
                im_host.connection_param[0].username = data_field
            elif header_field == HEADER_FIELD_PASSWORD:
                im_host.connection_param[0].password = data_field
            elif header_field == HEADER_FIELD_CONNECTION:
                im_host.connection_param[0].connection_type = data_field
            elif header_field == HEADER_FIELD_PORT:
                im_host.connection_param[0].port_number = remove_extra_spaces(data_field)

        # Import host already exists in the database, just update it
        if db_host is not None:
            db_host.platform = im_host.platform
            db_host.created_by = im_host.created_by

            if HEADER_FIELD_REGION in header_row:
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
    platform = SelectField('Platform', coerce=str,
                           choices=[(Platform.ASR9K, Platform.ASR9K),
                                    (Platform.CRS, Platform.CRS)])
    region = SelectField('Region', coerce=int, choices=[(-1, '')])
    data_list = TextAreaField('')
