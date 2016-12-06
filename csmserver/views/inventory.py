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
import csv

from flask import abort
from flask import Blueprint
from flask import render_template, jsonify, send_file
from flask.ext.login import login_required, current_user
from flask import request

from sqlalchemy import or_

from wtforms import Form
from wtforms import BooleanField
from wtforms import HiddenField
from wtforms import SelectField
from wtforms import StringField
from wtforms import TextAreaField
from wtforms.widgets import TextArea
from wtforms.validators import Length, required

from common import get_last_successful_inventory_elapsed_time
from common import get_user

from constants import UNKNOWN
from constants import ExportInformationFormat
from constants import UserPrivilege

from database import DBSession

from models import HostInventory, Inventory
from models import Host, Region
from models import SystemOption
from models import EmailJob
from models import logger

from report_writer import ExportInventoryInfoCSVWriter
from report_writer import ExportInventoryInfoHTMLWriter
from report_writer import ExportInventoryInfoExcelWriter
from report_writer import get_search_filter_in_html

inventory = Blueprint('inventory', __name__, url_prefix='/inventory')

HEADER_FIELD_SERIAL_NUMBER = 'serial_number'
HEADER_FIELD_MODEL_NAME = 'model_name'
HEADER_FIELD_NOTES = 'notes'


@inventory.route('/inventory_home')
@login_required
def inventory_home():
    return render_template('inventory/home.html', current_user=current_user)


@inventory.route('/query_add_inventory', methods=['GET', 'POST'])
@login_required
def query_add_inventory():
    """
    Provide service for user to:
    1. Query an inventory based on serial number.
    2. Add/Edit the inventory with input serial number, model name(optional), and notes(optional).
    3. Delete the inventory with input serial number.
    Any user can query the inventory, but only Admin user can add, update or delete inventory.
    """
    sn_form = QueryInventoryBySerialNumberForm(request.form)
    update_inventory_form = UpdateInventoryForm(request.form)

    inventory_data_fields = {'serial_number_submitted': None, 'new_inventory': False,
                             'inventory_name': None, 'description': None,
                             'hardware_revision': None, 'hostname': '', 'region_name': None,
                             'chassis': None, 'platform': None, 'software': None,
                             'last_successful_retrieval': None, 'inventory_retrieval_status': None}

    error_msg = None
    success_msg = None

    if request.method == 'GET':
        init_query_add_inventory_forms(sn_form, update_inventory_form)

    elif request.method == 'POST':
        db_session = DBSession()

        # if user submitted the form with the serial number
        # then we display back all the information for the inventory with this serial number
        if sn_form.hidden_submit_sn.data == 'True':
            get_inventory_data_by_serial_number(db_session, sn_form, update_inventory_form, inventory_data_fields)

        # if user submitted the form with the updated inventory info
        # we update/create or delete the inventory
        else:

            if current_user.privilege != UserPrivilege.ADMIN:
                error_msg = "User not authorized to create, update or delete inventory."

            # there is restriction on front end - serial_number submitted cannot be empty string, double check here
            elif update_inventory_form.hidden_serial_number.data:

                inventory_entry = db_session.query(Inventory).filter(
                    Inventory.serial_number == update_inventory_form.hidden_serial_number.data).first()

                if update_inventory_form.hidden_action.data == "Update":
                    update_or_add_inventory(db_session, inventory_entry, update_inventory_form.hidden_serial_number.data,
                                            update_inventory_form.model_name.data, update_inventory_form.notes.data)

                elif update_inventory_form.hidden_action.data == "Delete":
                    success_msg, error_msg = delete_inventory(db_session, inventory_entry)

                else:
                    error_msg = "Unknown request is received."
            else:
                error_msg = "Failed to create inventory because serial number submitted is empty."

            if not error_msg:
                # clear the forms to indicate a successful inventory update/add action!
                init_query_add_inventory_forms(sn_form, update_inventory_form)
            else:
                sn_form.serial_number.data = update_inventory_form.hidden_serial_number.data
                get_inventory_data_by_serial_number(db_session, sn_form, update_inventory_form, inventory_data_fields)

        db_session.close()

    return render_template('inventory/query_add_inventory.html', sn_form=sn_form,
                           update_inventory_form=update_inventory_form, success_msg=success_msg,
                           error_msg=error_msg, current_user=current_user, **inventory_data_fields)


def init_query_add_inventory_forms(sn_form, update_inventory_form):
    sn_form.serial_number.data = None
    sn_form.hidden_submit_sn.data = ''

    update_inventory_form.model_name.data = None
    update_inventory_form.notes.data = None
    update_inventory_form.hidden_serial_number.data = ''
    update_inventory_form.hidden_action.data = ''
    return


def get_inventory_data_by_serial_number(db_session, sn_form, update_inventory_form, inventory_data_fields):
    """
    Get the data fields for the queried inventory for the purpose of displaying to user
    :param db_session: session of database transactions
    :param sn_form: the form with the serial number input and etc.
    :param update_inventory_form: the form with model name, notes and etc.
    :param inventory_data_fields: the extra data fields that will be displayed to the user
    :return: None
    """

    inventory_data_fields['new_inventory'] = True

    existing_inventory = db_session.query(Inventory).filter(
        Inventory.serial_number == sn_form.serial_number.data).first()

    inventory_data_fields['serial_number_submitted'] = sn_form.serial_number.data

    if existing_inventory:
        inventory_data_fields['new_inventory'] = False
        update_inventory_form.model_name.data = existing_inventory.model_name
        update_inventory_form.notes.data = existing_inventory.notes

        inventory_data_fields['inventory_name'] = existing_inventory.name
        inventory_data_fields['description'] = existing_inventory.description
        inventory_data_fields['hardware_revision'] = existing_inventory.hardware_revision

        # if this inventory has been discovered in a host - host_id is not None
        if isinstance(existing_inventory.host_id, (int, long)):
            host = db_session.query(Host).filter(Host.id == existing_inventory.host_id).first()
            if host:
                inventory_data_fields['hostname'] = host.hostname
                inventory_data_fields['region_name'] = host.region.name if host.region is not None else UNKNOWN
                inventory_data_fields['chassis'] = UNKNOWN if host.platform is None else host.platform
                inventory_data_fields['platform'] = UNKNOWN if host.software_platform is None else host.software_platform
                inventory_data_fields['software'] = UNKNOWN if host.software_version is None else host.software_version

                inventory_job = host.inventory_job[0]
                if inventory_job and inventory_job.last_successful_time:
                    inventory_data_fields['last_successful_retrieval'] = get_last_successful_inventory_elapsed_time(host)
                    inventory_data_fields['inventory_retrieval_status'] = inventory_job.status

    return


def update_or_add_inventory(db_session, inventory_obj, serial_number, model_name, notes, commit=True):
    """
    Either update or add the inventory given serial number, model name(optional), and notes(optional)
    :param db_session: session of database transactions
    :param inventory_obj: the inventory row that we got from querying with the provided serial_number
    :param serial_number: input serial number string
    :param model_name: input model name string
    :param notes: input notes string
    :param commit: if true, commit the db transaction in the end, else, don't commit
    :return: None.
    """
    if inventory_obj:
        # if this inventory has been discovered in a host, model_name cannot be updated by user
        # there is restriction on front end, but double ensure it here
        if isinstance(inventory_obj.host_id, (int, long)):
            inventory_obj.update(db_session, notes=notes)

        # if this inventory is not found in a host, user can define/update the model_name
        else:
            inventory_obj.update(db_session, model_name=model_name, notes=notes)
        if commit:
            db_session.commit()
    else:
        inv = Inventory(serial_number=serial_number,
                        model_name=model_name,
                        notes=notes)
        db_session.add(inv)
        if commit:
            db_session.commit()
    return


def delete_inventory(db_session, inventory_obj):
    """
    Delete the inventory with the input serial number from the inventory table
    :param db_session: session of database transactions
    :param inventory_obj: the inventory row that we got from querying with the provided serial_number
    :return: success_msg, error_msg. Can either be None or strings.
    """
    success_msg = None
    error_msg = None

    if inventory_obj:
        if isinstance(inventory_obj.host_id, (int, long)):
            error_msg = "Cannot delete this inventory because CSM inventory retrieval " + \
                        "indicates that it is currently used by a device."
        else:
            db_session.delete(inventory_obj)
            db_session.commit()
            success_msg = "Inventory with serial number '{}' ".format(inventory_obj.serial_number) + \
                "has been successfully deleted."
    else:
        error_msg = "Cannot delete this inventory because it is not " + \
                    "saved in CSM inventory database yet."

    return success_msg, error_msg


@inventory.route('/search_inventory', methods=['GET', 'POST'])
@login_required
def search_inventory():
    search_inventory_form = SearchInventoryForm(request.form)
    export_results_form = ExportInventoryInformationForm(request.form)

    export_results_form.user_email.data = current_user.email if current_user.email else ""

    return render_template('inventory/search_inventory.html', search_inventory_form=search_inventory_form,
                           export_results_form=export_results_form, current_user=current_user)


def query_available_inventory(db_session, serial_number, model_names, partial_model_names):
    """
    Search for the available inventories matching the selected filters. Only serial number, model name(s),
    or partial model name(s) apply to this search.
    :param db_session: db transaction session
    :param serial_number: a string containing serial number
    :param model_names: an array of strings - selected model names - to filter inventories with
    :param partial_model_names: an array of strings - partial model names - to filter inventories with
    :return: query object/iterator that contains the result of the available inventories matching
            the search criteria.
    """
    filter_clauses = [Inventory.host_id == None]
    get_filter_clauses_for_serial_number_model_name(serial_number,
                                                    model_names,
                                                    partial_model_names,
                                                    Inventory, filter_clauses)

    return db_session.query(Inventory).filter(*filter_clauses)


def query_in_use_inventory(db_session, json_data):
    """
    Search for the in-use inventories matching the selected filters.
    :param db_session: db transaction session
    :param json_data: a dictionary containing all search criteria.
    :return: query object/iterator that contains the result of the in-use inventories matching
            the search criteria.
    """
    filter_clauses = []
    filter_clauses = get_filter_clauses_for_serial_number_model_name(json_data.get('serial_number'),
                                                                     json_data.get('model_names'),
                                                                     json_data.get('partial_model_names'),
                                                                     HostInventory, filter_clauses)
    results = db_session.query(HostInventory).filter(*filter_clauses)

    join_filter_clauses = []
    if json_data.get('region_ids'):
        join_filter_clauses.append(Host.region_id.in_(map(int, json_data.get('region_ids'))))

    if json_data.get('chassis_types'):
        join_filter_clauses.append(Host.platform.in_(json_data.get('chassis_types')))

    if json_data.get('software_versions'):
        join_filter_clauses.append(Host.software_version.in_(json_data.get('software_versions')))

    return results.join(Host, HostInventory.host_id == Host.id).filter(*join_filter_clauses)


def get_filter_clauses_for_serial_number_model_name(serial_number, model_names, partial_model_names,
                                                    filter_table, filter_clauses):
    """
    helper function to api_search_inventory, create filter clauses for selected
    serial number and an array of selected model names or an array of entered
    partial model names.
    """
    if serial_number:
        filter_clauses.append(filter_table.serial_number == serial_number)

    if model_names:
        filter_clauses.append(filter_table.model_name.in_(model_names))

    elif partial_model_names:
        filter_clause = get_filter_clauses_for_partial_field_match(filter_table.model_name,
                                                                   partial_model_names)
        # cannot do 'if filter_clause' because ClauseElement
        # raises an exception if called in a boolean context
        if filter_clause is not None:
            filter_clauses.append(filter_clause)
    return filter_clauses


def get_filter_clauses_for_partial_field_match(field, partial_strings_array):
    """
    Create filter clauses for partially matching the field to any of the
    strings in an array using LIKE
    """
    clauses = []
    for partial_string in partial_strings_array:
        stripped_partial_string = partial_string.strip()
        if stripped_partial_string:
            clauses.append(field.like('%' + stripped_partial_string + '%'))
    if len(clauses) == 0:
        return None
    elif len(clauses) == 1:
        return clauses[0]

    return or_(*clauses)


@inventory.route('/export', methods=['POST'])
@login_required
def export_inventory_information():
    """export the inventory search result to html or excel format."""
    db_session = DBSession()
    export_results_form = ExportInventoryInformationForm(request.form)

    export_data = dict()
    export_data['export_format'] = export_results_form.export_format.data
    export_data['serial_number'] = export_results_form.hidden_serial_number.data
    export_data['region_ids'] = export_results_form.hidden_region_ids.data.split(',') \
        if export_results_form.hidden_region_ids.data else []
    export_data['chassis_types'] = export_results_form.hidden_chassis_types.data.split(',') \
        if export_results_form.hidden_chassis_types.data else []
    export_data['software_versions'] = export_results_form.hidden_software_versions.data.split(',') \
        if export_results_form.hidden_software_versions.data else []
    export_data['model_names'] = export_results_form.hidden_model_names.data.split(',') \
        if export_results_form.hidden_model_names.data else []
    export_data['partial_model_names'] = export_results_form.hidden_partial_model_names.data.split(',') \
        if export_results_form.hidden_partial_model_names.data else []

    if export_data['region_ids']:
        region_names = db_session.query(Region.name).filter(
            Region.id.in_(map(int, export_data['region_ids']))).order_by(Region.name.asc()).all()
        export_data['region_names'] = []
        [export_data['region_names'].append(query_tuple[0]) for query_tuple in region_names]
    else:
        export_data['region_names'] = []

    export_data['available_inventory_iter'] = query_available_inventory(db_session,
                                                                        export_data.get('serial_number'),
                                                                        export_data.get('model_names'),
                                                                        export_data.get('partial_model_names'))

    export_data['in_use_inventory_iter'] = query_in_use_inventory(db_session, export_data)

    export_data['user'] = current_user

    writer = None
    if export_data.get('export_format') == ExportInformationFormat.HTML:
        writer = ExportInventoryInfoHTMLWriter(**export_data)
    elif export_data.get('export_format') == ExportInformationFormat.MICROSOFT_EXCEL:
        writer = ExportInventoryInfoExcelWriter(**export_data)
    elif export_data.get('export_format') == ExportInformationFormat.CSV:
        writer = ExportInventoryInfoCSVWriter(**export_data)

    if writer:
        file_path = writer.write_report()

        if export_results_form.send_email.data:
            email_message = "<html><head></head><body>Please find in the attachment the inventory search results " \
                            "matching the following search criteria: "
            search_criteria_in_html = get_search_filter_in_html(export_data)
            if search_criteria_in_html:
                email_message += search_criteria_in_html + '</body></html>'
            else:
                email_message += '&nbsp;None</body></html>'
            create_email_job_with_attachment_files(db_session, email_message, file_path,
                                                   export_results_form.user_email.data)

        return send_file(file_path, as_attachment=True)

    logger.error('inventory: invalid export format "%s" chosen.' % export_data.get('export_format'))
    return


@inventory.route('/api/check_if_email_notify_enabled/')
@login_required
def check_if_email_notify_enabled():
    db_session = DBSession()
    system_option = SystemOption.get(db_session)
    db_session.close()
    return jsonify({'email_notify_enabled': system_option.enable_email_notify})


def create_email_job_with_attachment_files(db_session, message, file_paths, recipients):
    system_option = SystemOption.get(db_session)
    if not system_option.enable_email_notify:
        return

    email_job = EmailJob(recipients=recipients, message=message, created_by=current_user.username,
                         attachment_file_paths=file_paths)
    db_session.add(email_job)
    db_session.commit()
    return


@inventory.route('/import_inventory')
@login_required
def import_inventory():
    if current_user.privilege != UserPrivilege.ADMIN:
        abort(401)

    form = ImportInventoryForm(request.form)

    return render_template('inventory/import_inventory.html', form=form)


@inventory.route('/api/import_inventory', methods=['POST'])
@login_required
def api_import_inventory():
    """
    API for importing inventory
    Note: 1. If inventory already exists in db, and the model name has been discovered
         by CSM, we will not overwrite the model name with data from here.
         2. For data with duplicate serial numbers, only the first data entry will be created
         in db or used to update an existing inventory.
    return either status: OK with unimported_inventory: list of unimported data rows
                                                        (for noting duplicated serial numbers)
           or status: errors in the imported data separated by comma's
    """
    if current_user.privilege != UserPrivilege.ADMIN:
        abort(401)
    importable_header = [HEADER_FIELD_SERIAL_NUMBER, HEADER_FIELD_MODEL_NAME, HEADER_FIELD_NOTES]
    general_notes = request.form['general_notes']
    data_list = request.form['data_list']

    db_session = DBSession()

    reader = csv.reader(data_list.splitlines(), delimiter=',')
    header_row = next(reader)

    # Check mandatory data fields
    error = []
    if HEADER_FIELD_SERIAL_NUMBER not in header_row:
        error.append('"serial_number" is missing in the header.')

    for header_field in header_row:
        if header_field not in importable_header:
            error.append('"' + header_field + '" is not a valid header field.')

    if error:
        return jsonify({'status': ','.join(error)})

    row = 2
    # already checked that HEADER_FIELD_SERIAL_NUMBER is in header
    serial_number_idx = header_row.index(HEADER_FIELD_SERIAL_NUMBER)

    data_list = list(reader)

    # Check if each row has the same number of data fields as the header
    for row_data in data_list:
        if len(row_data) > 0:
            if len(row_data) != len(header_row):
                error.append('line %d has wrong number of data fields.' % row)
            else:
                if not row_data[serial_number_idx]:
                    error.append('line %d missing serial number value.' % row)
        row += 1

    if error:
        return jsonify({'status': ','.join(error)})

    # Import the data
    unique_serial_numbers = set()
    unimported_inventory = []
    row = 1
    for data in data_list:
        row += 1
        if len(data) == 0:
            continue

        serial_number = ''
        model_name = ''
        notes = general_notes

        for column in range(len(header_row)):

            header_field = header_row[column]
            data_field = data[column].strip()

            if header_field == HEADER_FIELD_SERIAL_NUMBER:
                serial_number = data_field
            elif header_field == HEADER_FIELD_MODEL_NAME:
                model_name = data_field
            elif header_field == HEADER_FIELD_NOTES and data_field:
                notes = data_field

        if serial_number:
            inventory_obj = db_session.query(Inventory).filter(Inventory.serial_number == serial_number).first()
            # only create/update inventory data if the serial number is unique among the imported data
            if serial_number not in unique_serial_numbers:
                update_or_add_inventory(db_session, inventory_obj, serial_number, model_name, notes, commit=False)
                unique_serial_numbers.add(serial_number)
            else:
                unimported_inventory.append('line %d: ' % row + ','.join(data))
        else:
            return jsonify({'status': 'Serial number data field cannot be empty.'})

    db_session.commit()
    db_session.close()

    if unimported_inventory:
        return jsonify({'status': 'OK', 'unimported_inventory': unimported_inventory})

    return jsonify({'status': 'OK', 'unimported_inventory': []})


@inventory.route('/api/get_chassis_types/')
@login_required
def api_get_chassis():
    """
    This method is called by ajax attached to Select2.
    The returned JSON contains the predefined tags.
    """
    return update_select2_options(request.args, Host.platform)


@inventory.route('/api/get_software_versions/')
@login_required
def api_get_software_versions():
    """
    This method is called by ajax attached to Select2.
    The returned JSON contains the predefined tags.
    """
    return update_select2_options(request.args, Host.software_version)


@inventory.route('/api/get_model_names/')
@login_required
def api_get_model_names():
    """
    This method is called by ajax attached to Select2.
    The returned JSON contains the predefined tags.
    """
    return update_select2_options(request.args, Inventory.model_name)


def update_select2_options(request_args, data_field):
    """
    This method helps populate the options used by ajax attached to Select2.
    The returned JSON contains the predefined tags.
    """
    db_session = DBSession()

    rows = []
    criteria = '%'
    if len(request_args) > 0:
        criteria += request_args.get('q') + '%'

    item_iter = db_session.query(data_field).filter(data_field.like(criteria)).distinct().order_by(data_field.asc())

    for item in item_iter:
        if item[0]:
            rows.append({'id': item[0], 'text': item[0]})

    return jsonify(**{'data': rows})


class ExportInventoryInformationForm(Form):
    export_format = SelectField('Export Format', coerce=str,
                                choices=[(ExportInformationFormat.CSV,
                                          ExportInformationFormat.CSV),
                                         (ExportInformationFormat.HTML,
                                          ExportInformationFormat.HTML),
                                         (ExportInformationFormat.MICROSOFT_EXCEL,
                                          ExportInformationFormat.MICROSOFT_EXCEL)])
    send_email = BooleanField('Email Export Data')
    user_email = StringField('User Email')
    hidden_serial_number = HiddenField('')
    hidden_region_ids = HiddenField('')
    hidden_chassis_types = HiddenField('')
    hidden_software_versions = HiddenField('')
    hidden_model_names = HiddenField('')
    hidden_partial_model_names = HiddenField('')


class QueryInventoryBySerialNumberForm(Form):
    serial_number = StringField('Serial Number', [required(), Length(max=50)])
    hidden_submit_sn = HiddenField('')


class UpdateInventoryForm(Form):
    model_name = StringField('Model Name (PID)', [Length(max=50)])
    notes = StringField('Notes', widget=TextArea())
    hidden_serial_number = HiddenField('')
    hidden_action = HiddenField('')


class SearchInventoryForm(Form):
    serial_number = StringField('Serial Number', [Length(max=50)])
    partial_model_names = StringField('Model Name (PID)')


class ImportInventoryForm(Form):
    general_notes = TextAreaField('')
    data_list = TextAreaField('')
