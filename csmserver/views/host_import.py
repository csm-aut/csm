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
from common import get_region_by_id
from common import get_host

from models import InventoryJob
from models import Host
from models import ConnectionParam

from database import DBSession

from utils import remove_extra_spaces

import csv

host_import = Blueprint('host_import', __name__, url_prefix='/host_import')


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


@host_import.route('/api/import_hosts', methods=['POST'])
@login_required
def api_import_hosts():
    db_session = DBSession()

    expected_header = 'hostname,roles,ip,username,password,connection,port'.split(',')
    platform = request.form['platform']
    region_id = request.form['region']
    data_list = request.form['data_list']

    region = get_region_by_id(db_session, region_id)
    if region is None:
        return jsonify({'status': 'Region is no longer exists in the database.'})

    header = None
    error = None
    im_hosts = []
    row_number = 0

    reader = csv.reader(data_list.split('\n'), delimiter=',')
    for row in reader:
        row_number += 1

        if row_number == 1:
            # Check if header is correct
            header = row
            if 'hostname' not in header:
                error = '"hostname" is missing in the header.'
                break

            if 'ip' not in header:
                error = '"ip" is missing in the header.'
                break

            if 'connection' not in header:
                error = '"connection" is missing in the header.'
                break

            for header_field in header:
                if header_field not in expected_header:
                    error = header_field + ' is not a correct header field.'
                    break
        else:
            if len(row) > 0:
                if (len(row) != len(header)):
                    error = '"' + ','.join(row) + '" has wrong number of data fields.'
                    break

                im_host = Host()
                im_host.platform = platform
                im_host.region_id = region_id
                im_host.created_by = current_user.username
                im_host.inventory_job.append(InventoryJob())
                im_host.connection_param.append(ConnectionParam())

                im_host.connection_param[0].username = ''
                im_host.connection_param[0].password = ''

                for column in range(len(header)):

                    header_field = header[column]
                    data_field = row[column]

                    if header_field == 'hostname':
                        # Check if the hostname exists already
                        if get_host(db_session, data_field) is not None:
                            error = 'hostname "' + data_field + '" already exists in the database.'
                            break

                        if data_field in im_hosts:
                            error = 'hostname "' + data_field + '" already exists in the import data.'
                            break

                        im_hosts.append(data_field)
                        im_host.hostname = data_field
                    elif header_field == 'ip':
                        im_host.connection_param[0].host_or_ip = remove_extra_spaces(data_field)
                    elif header_field == 'username':
                        im_host.connection_param[0].username = data_field
                    elif header_field == 'password':
                        im_host.connection_param[0].password = data_field
                    elif header_field == 'connection':
                        if data_field != ConnectionType.TELNET and data_field != ConnectionType.SSH:
                            error = '"' + ','.join(row) + '" has a wrong connection type (should be "telnet" or "ssh").'
                            break
                        im_host.connection_param[0].connection_type = data_field
                    elif header_field == 'port':
                        im_host.connection_param[0].port_number = remove_extra_spaces(data_field)
                    elif header_field == 'roles':
                        im_host.roles = remove_extra_spaces(data_field)


                # Add the import host
                db_session.add(im_host)

    if error is not None:
        return jsonify({'status': error})
    else:
        db_session.commit()
        return jsonify({'status': 'OK'})


class HostImportForm(Form):
    platform = SelectField('Platform', coerce=str,
                           choices=[(Platform.ASR9K, Platform.ASR9K),
                                    (Platform.CRS, Platform.CRS)])
    region = SelectField('Region', coerce=int, choices=[(-1, '')])
    data_list = TextAreaField('Comma Delimited Fields')
