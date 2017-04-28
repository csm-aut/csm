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
from flask import render_template, jsonify, abort, send_file, flash
from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for

from wtforms import Form
from wtforms import StringField
from wtforms import SelectField
from wtforms import TextAreaField
from wtforms import RadioField
from wtforms import HiddenField
from wtforms import SelectMultipleField
from wtforms.validators import Length, required

from models import logger
from models import SoftwareProfile
from models import SystemOption
from models import ConformanceReport
from models import ConformanceReportEntry

from common import get_last_successful_inventory_elapsed_time
from common import get_host_active_packages
from common import get_host_inactive_packages
from common import fill_servers
from common import get_server_list
from common import get_host
from common import create_or_update_install_job
from common import fill_custom_command_profiles
from common import can_delete
from common import can_create
from common import can_install
from common import get_conformance_report_by_id
from common import get_software_profile
from common import get_software_profile_list
from common import get_software_profile_by_id
from common import delete_software_profile
from common import get_host_list_by
from common import get_hosts_by_software_profile_id

from database import DBSession

from constants import UNKNOWN
from constants import HostConformanceStatus
from constants import InstallAction
from constants import JobStatus
from constants import get_temp_directory

from conformance_report import ConformanceReportWriter
from filters import get_datetime_string

from smu_info_loader import SMUInfoLoader

from forms import ServerDialogForm

from utils import is_empty
from utils import create_temp_user_directory
from utils import create_directory
from utils import make_file_writable

from package_utils import strip_smu_file_extension

import os
import json
import re
import datetime

conformance = Blueprint('conformance', __name__, url_prefix='/conformance')


@conformance.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if not can_install(current_user):
        abort(401)

    msg = ''
    # Software Profile import
    if request.method == 'POST':
        file = request.files['file']
        if file:
            if not allowed_file(file.filename):
                msg = "Incorrect file format -- " + file.filename + " must be .json"
            else:
                file_path = os.path.join(get_temp_directory(), "software_profiles.json")
                file.save(file_path)
                failed = ""

                with open(file_path, 'r') as f:
                    try:
                        s = json.load(f)
                    except:
                        msg = "Incorrect file format -- " + file.filename + " must be a valid JSON file."
                        flash(msg, 'import_feedback')
                        return redirect(url_for(".home"))

                    if "CSM Server:Software Profile" not in s.keys():
                        msg = file.filename + " is not in the correct Software Profile format."
                    else:
                        db_session = DBSession
                        profiles = [p for (p,) in DBSession().query(SoftwareProfile.name).all()]
                        d = s["CSM Server:Software Profile"]

                        for software_profile_name in d.keys():
                            name = ''
                            if software_profile_name in profiles:
                                name = software_profile_name
                                # Will keep appending ' - copy' until it hits a unique name
                                while name in profiles:
                                    name += " - copy"
                                msg += software_profile_name + ' -> ' + name + '\n'
                                profiles.append(name)

                            if len(name) < 100 and len(software_profile_name) < 100:
                                try:
                                    profile = SoftwareProfile(
                                        name=name if name else software_profile_name,
                                        packages=d[software_profile_name],
                                        created_by=current_user.username
                                    )
                                    db_session.add(profile)
                                    db_session.commit()
                                except:
                                    failed += software_profile_name + '\n'
                            else:
                                failed += software_profile_name + ' (name too long)\n'

                        if msg:
                            msg = "The following profiles already exist and will try to be imported under modified " \
                                  "names:\n\n" + msg + '\n'
                            if failed:
                                msg += 'The following profiles failed to import:\n\n' + failed
                        elif failed:
                            msg = 'The following profiles failed to import:\n\n' + failed
                        else:
                            msg = "Software Profile import was successful!"

                # delete file
                os.remove(file_path)

            flash(msg, 'import_feedback')
            return redirect(url_for(".home"))

    db_session = DBSession()

    conformance_form = ConformanceForm(request.form)
    assign_software_profile_to_hosts_form = AssignSoftwareProfileToHostsForm(request.form)
    view_host_software_profile_form = ViewHostSoftwareProfileForm(request.form)
    conformance_report_dialog_form = ConformanceReportDialogForm(request.form)
    make_conform_dialog_form = MakeConformDialogForm(request.form)
    batch_make_conform_dialog_form = BatchMakeConformDialogForm(request.form)

    fill_custom_command_profiles(db_session, make_conform_dialog_form.custom_command_profile.choices)
    fill_custom_command_profiles(db_session, batch_make_conform_dialog_form.batch_custom_command_profile.choices)

    export_conformance_report_form = ExportConformanceReportForm(request.form)
    export_conformance_report_form.include_host_packages.data = True
    export_conformance_report_form.exclude_conforming_hosts.data = True

    return render_template('conformance/index.html',
                           conformance_form=conformance_form,
                           assign_software_profile_to_hosts_form=assign_software_profile_to_hosts_form,
                           view_host_software_profile_form=view_host_software_profile_form,
                           conformance_report_dialog_form=conformance_report_dialog_form,
                           install_actions=[InstallAction.PRE_UPGRADE, InstallAction.INSTALL_ADD,
                                            InstallAction.INSTALL_ACTIVATE, InstallAction.POST_UPGRADE,
                                            InstallAction.INSTALL_COMMIT, InstallAction.ALL],
                           make_conform_dialog_form=make_conform_dialog_form,
                           batch_make_conform_dialog_form=batch_make_conform_dialog_form,
                           export_conformance_report_form=export_conformance_report_form,
                           server_time=datetime.datetime.utcnow(),
                           system_option=SystemOption.get(DBSession()))


@conformance.route('/software_profile/create', methods=['GET', 'POST'])
@login_required
def software_profile_create():
    if not can_create(current_user):
        abort(401)

    db_session = DBSession()

    form = SoftwareProfileForm(request.form)
    server_dialog_form = ServerDialogForm(request.form)

    fill_servers(server_dialog_form.server_dialog_server.choices, get_server_list(db_session), False)

    if request.method == 'POST' and form.validate():

        software_profile = get_software_profile(db_session, form.software_profile_name.data)

        if software_profile is not None:
            return render_template('conformance/software_profile_edit.html',
                                   form=form, system_option=SystemOption.get(db_session), duplicate_error=True)

        software_profile = SoftwareProfile(
            name=form.software_profile_name.data,
            packages=','.join([l for l in form.software_packages.data.splitlines() if l]),
            created_by=current_user.username)

        db_session.add(software_profile)
        db_session.commit()

        return redirect(url_for('conformance.home'))
    else:

        return render_template('conformance/software_profile_edit.html',
                               form=form, server_dialog_form=server_dialog_form,
                               system_option=SystemOption.get(db_session))


@conformance.route('/software_profile/<software_profile_name>/edit', methods=['GET', 'POST'])
@login_required
def software_profile_edit(software_profile_name):
    db_session = DBSession()

    software_profile = get_software_profile(db_session, software_profile_name)
    if software_profile is None:
        abort(404)

    form = SoftwareProfileForm(request.form)
    server_dialog_form = ServerDialogForm(request.form)
    fill_servers(server_dialog_form.server_dialog_server.choices, get_server_list(db_session), False)

    if request.method == 'POST' and form.validate():
        if software_profile_name != form.software_profile_name.data and \
                        get_software_profile(db_session, form.software_profile_name.data) is not None:
            return render_template('conformance/profile_edit.html',
                                   form=form, server_dialog_form=server_dialog_form,
                                   system_option=SystemOption.get(db_session), duplicate_error=True)

        software_profile.name = form.software_profile_name.data
        software_profile.packages = ','.join([l for l in form.software_packages.data.splitlines() if l]),

        db_session.commit()

        return redirect(url_for('conformance.home'))
    else:
        form.software_profile_name.data = software_profile.name
        if software_profile.packages is not None:
            form.software_packages.data = '\n'.join(software_profile.packages.split(','))

    return render_template('conformance/software_profile_edit.html',
                           form=form, server_dialog_form=server_dialog_form,
                           system_option=SystemOption.get(db_session))


@conformance.route('/api/get_software_profiles')
@login_required
def api_get_software_profiles():
    rows = []
    db_session = DBSession()

    software_profiles = get_software_profile_list(db_session)
    for software_profile in software_profiles:
        row = {'software_profile_id': software_profile.id,
               'software_profile_name': software_profile.name,
               'packages': software_profile.packages,
               'created_by': software_profile.created_by}

        rows.append(row)

    return jsonify(**{'data': rows})


@conformance.route('/api/get_software_profile/software_profile/<int:id>')
@login_required
def api_get_software_profile(id):
    rows = []
    db_session = DBSession()

    software_profile = get_software_profile_by_id(db_session, id)
    if software_profile:
        for package in software_profile.packages.split(','):
            rows.append({'package': package})

    return jsonify(**{'data': rows})


@conformance.route('/api/create_software_profile', methods=['POST'])
@login_required
def api_create_software_profile():
    if not can_create(current_user):
        abort(401)

    software_profile_name = request.form['software_profile_name']
    software_packages = request.form['software_packages']

    db_session = DBSession()

    software_profile = get_software_profile(db_session, software_profile_name)

    if software_profile is not None:
        return jsonify({'status': 'Software profile "' + software_profile_name +
                        '" already exists.  Use a different name instead.'})

    software_profile = SoftwareProfile(
        name=software_profile_name,
        packages=','.join([l for l in software_packages.splitlines() if l]),
        created_by=current_user.username)

    db_session.add(software_profile)
    db_session.commit()

    return jsonify({'status': 'OK'})


@conformance.route('/software_profile/<software_profile_name>/delete', methods=['DELETE'])
@login_required
def software_profile_delete(software_profile_name):
    if not can_delete(current_user):
        abort(401)

    db_session = DBSession()

    try:
        delete_software_profile(db_session, software_profile_name)
        return jsonify({'status': 'OK'})
    except Exception as e:
        logger.exception('software_profile_delete hit exception.')
        return jsonify({'status': e.message})


@conformance.route('/api/rerun_conformance_report/report/<int:id>')
@login_required
def api_rerun_conformance_report(id):
    db_session = DBSession()

    conformance_report = get_conformance_report_by_id(db_session, id)
    if conformance_report is not None:
        software_profile = get_software_profile(db_session, conformance_report.software_profile)
        if software_profile:
            return run_conformance_report(db_session, software_profile,
                                          conformance_report.match_criteria,
                                          conformance_report.hostnames.split(','))
        else:
            jsonify({'status': 'Unable to locate the software_profile with id = %s' % conformance_report.software_profile})
    else:
        jsonify({'status': 'Unable to locate the conformance report with id = %d' % id})

    return jsonify({'status': 'OK'})


@conformance.route('/api/run_conformance_report', methods=['POST'])
@login_required
def api_run_conformance_report():
    db_session = DBSession()
    software_profile_id = request.form['software_profile_id']
    match_criteria = request.form['match_criteria']
    hostnames = request.form.getlist('selected_hosts[]')

    software_profile = get_software_profile_by_id(db_session, software_profile_id)
    if not software_profile:
        return jsonify({'status': 'Unable to locate the software profile %d' % software_profile_id})

    return run_conformance_report(db_session, software_profile, match_criteria, hostnames)


@conformance.route('/api/run_conformance_report_that_match_host_software_profile', methods=['POST'])
@login_required
def api_run_conformance_report_that_match_host_software_profile():
    db_session = DBSession()
    software_profile_id = request.form['software_profile_id']
    match_criteria = request.form['match_criteria']

    software_profile = get_software_profile_by_id(db_session, software_profile_id)
    if not software_profile:
        return jsonify({'status': 'Unable to locate the software profile %d' % software_profile_id})

    hostnames = []
    hosts = get_hosts_by_software_profile_id(db_session, software_profile.id)
    for host in hosts:
        hostnames.append(host.hostname)

    return run_conformance_report(db_session, software_profile, match_criteria, hostnames)


def run_conformance_report(db_session, software_profile, match_criteria, hostnames):
    """
    software_profile: SoftwareProfile instance
    hostnames: a list of hostnames
    """
    host_not_in_conformance = 0
    host_out_dated_inventory = 0

    software_profile_packages = software_profile.packages.split(',')

    conformance_report = ConformanceReport(
        software_profile=software_profile.name,
        software_profile_packages=','.join(sorted(software_profile_packages)),
        match_criteria=match_criteria,
        hostnames=','.join(hostnames),
        user_id=current_user.id,
        created_by=current_user.username)

    software_profile_package_dict = fixup_software_profile_packages(software_profile_packages)

    for hostname in hostnames:
        host = get_host(db_session, hostname)
        if host:
            inventory_job = host.inventory_job[0]

            comments = ''
            if inventory_job is not None and inventory_job.last_successful_time is not None:
                comments = '(' + get_last_successful_inventory_elapsed_time(host) + ')'

            if inventory_job.status != JobStatus.COMPLETED:
                comments += ' *'
                host_out_dated_inventory += 1

            host_packages = []
            if match_criteria == 'inactive':
                host_packages = get_host_inactive_packages(hostname)
            elif match_criteria == 'active':
                host_packages = get_host_active_packages(hostname)

            missing_packages = get_missing_packages(host_packages, software_profile_package_dict)

            if missing_packages:
                host_not_in_conformance += 1

            conformed = False
            if len(host_packages) > 0 and len(missing_packages) == 0:
                conformed = True

            conformance_report_entry = ConformanceReportEntry(
                hostname=hostname,
                software_platform=UNKNOWN if host.software_platform is None else host.software_platform,
                software_version=UNKNOWN if host.software_version is None else host.software_version,
                conformed=HostConformanceStatus.CONFORM if conformed else HostConformanceStatus.NON_CONFORM,
                comments=comments,
                host_packages=','.join(sorted(get_match_result(host_packages,
                                                               software_profile_package_dict.values()))),
                missing_packages=','.join(sorted(missing_packages)))
        else:
            # Flag host not found condition
            host_out_dated_inventory += 1
            host_not_in_conformance += 1

            conformance_report_entry = ConformanceReportEntry(
                hostname=hostname,
                software_platform='MISSING',
                software_version='MISSING',
                host_packages='MISSING',
                missing_packages='MISSING')

        conformance_report.entries.append(conformance_report_entry)

    conformance_report.host_not_in_conformance = host_not_in_conformance
    conformance_report.host_out_dated_inventory = host_out_dated_inventory

    db_session.add(conformance_report)
    db_session.commit()

    purge_old_conformance_reports(db_session)

    return jsonify({'status': 'OK'})


def purge_old_conformance_reports(db_session):
    conformance_reports = get_conformance_report_by_user(db_session, current_user.username)
    if len(conformance_reports) > 10:
        try:
            # delete the earliest conformance report.
            db_session.delete(conformance_reports[-1])
            db_session.commit()
        except Exception:
            logger.exception('purge_old_conformance_reports() hit exception')


def get_match_result(host_packages, software_profile_packages):
    match_result = []

    for host_package in host_packages:
        for software_profile_package in software_profile_packages:
            matched = False
            if re.search(software_profile_package, host_package) is not None:
                matched = True
                break

        match_result.append(host_package + ' (matched)' if matched else host_package)

    return match_result


def get_missing_packages(host_packages, software_profile_package_dict):
    missing_packages = []

    for software_profile_package, package_name_to_match in software_profile_package_dict.iteritems():
        matched = False
        for host_package in host_packages:
            if re.search(package_name_to_match, host_package) is not None:
                matched = True
                break

        if not matched:
            missing_packages.append(software_profile_package)

    return missing_packages


def fixup_software_profile_packages(software_profile_packages):
    """
    Unfortunately, some of the software packages have different external name and internal name (after activation)
    External Name: asr9k-asr9000v-nV-px.pie-6.1.2
    Internal Name: asr9k-9000v-nV-px-6.1.2

    External Name: asr9k-services-infra-px.pie-5.3.4
    Internal Name: asr9k-services-infra.pie-5.3.4

    Returns dictionary with key = software_profile_package, value = package_name_to_match
    """
    result_dict = dict()

    for software_profile_package in software_profile_packages:
        # FIXME: Need platform specific logic
        package_name_to_match = strip_smu_file_extension(software_profile_package).replace('.x86_64', '')

        if 'asr9000v' in package_name_to_match:
            package_name_to_match = package_name_to_match.replace('asr9000v', '9000v')
        elif 'services-infra-px' in package_name_to_match:
            package_name_to_match = package_name_to_match.replace('-px', '')

        result_dict[software_profile_package] = package_name_to_match

    return result_dict


@conformance.route('/api/export_conformance_report/report/<int:id>')
@login_required
def api_export_conformance_report(id):
    locale_datetime = request.args.get('locale_datetime')
    include_host_packages = request.args.get('include_host_packages')
    exclude_conforming_hosts = request.args.get('exclude_conforming_hosts')
    db_session = DBSession()

    conformance_report = get_conformance_report_by_id(db_session, id)
    file_path = None
    if conformance_report is not None:
        writer = ConformanceReportWriter(user=current_user,
                                         conformance_report=conformance_report,
                                         locale_datetime=locale_datetime,
                                         include_host_packages=bool(int(include_host_packages)),
                                         exclude_conforming_hosts=bool(int(exclude_conforming_hosts)))
        file_path = writer.write_report()

    return send_file(file_path, as_attachment=True)


@conformance.route('/api/get_conformance_report_summary/report/<int:id>')
@login_required
def api_get_conformance_report_summary(id):
    db_session = DBSession()
    conformance_report = get_conformance_report_by_id(db_session, id)

    if conformance_report is not None:
        return jsonify(**{'data': [
            {'total_hosts': 0 if is_empty(conformance_report.hostnames) else len(conformance_report.hostnames.split(',')),
             'host_not_in_conformance': conformance_report.host_not_in_conformance,
             'host_out_dated_inventory': conformance_report.host_out_dated_inventory,
             'match_criteria': (conformance_report.match_criteria + ' Packages').title()}
        ]})
    else:
        return jsonify({'status': 'Failed'})


@conformance.route('/api/get_conformance_report_datetime/report/<int:id>')
@login_required
def api_get_conformance_report_datetime(id):
    conformance_report_datetime = None
    db_session = DBSession()

    conformance_report = get_conformance_report_by_id(db_session, id)
    if conformance_report is not None:
        conformance_report_datetime = get_datetime_string(conformance_report.created_time)

    return jsonify(**{'data': [
        {'conformance_report_datetime': conformance_report_datetime}
    ]})


@conformance.route('/api/get_non_conforming_hosts/report/<int:id>')
@login_required
def api_get_non_conforming_hosts(id):
    rows = []
    db_session = DBSession()

    conformance_report_entries = db_session.query(ConformanceReportEntry).\
        filter(ConformanceReportEntry.conformance_report_id == id).all()

    for conformance_report_entry in conformance_report_entries:
        if conformance_report_entry.conformed == 'No':
            rows.append({'hostname': conformance_report_entry.hostname})

    return jsonify(**{'data': rows})


@conformance.route('/api/get_conformance_report_software_profile_packages/report/<int:id>')
@login_required
def api_get_conformance_report_software_profile_packages(id):
    rows = []
    db_session = DBSession()

    conformance_report = get_conformance_report_by_id(db_session, id)
    if conformance_report is not None:
        software_profile_packages = conformance_report.software_profile_packages.split(',')

        smu_loader = None
        platform, release = SMUInfoLoader.get_platform_and_release(software_profile_packages)
        if platform != UNKNOWN and release != UNKNOWN:
            smu_loader = SMUInfoLoader(platform, release)

        for software_profile_package in software_profile_packages:
            description = ''
            if smu_loader is not None and smu_loader.is_valid:
                smu_info = smu_loader.get_smu_info(software_profile_package.replace('.' + smu_loader.file_suffix,''))
                if smu_info is not None:
                    description = smu_info.description

            rows.append({'software_profile_package': software_profile_package,
                         'description': description})

    return jsonify(**{'data': rows})


@conformance.route('/api/get_conformance_report_dates')
@login_required
def api_get_conformance_report_dates():
    rows = []
    db_session = DBSession()

    conformance_reports = get_conformance_report_by_user(db_session, current_user.username)
    if conformance_reports:
        for conformance_report in conformance_reports:
            row = {'id': conformance_report.id, 'software_profile': conformance_report.software_profile,
                   'created_time': conformance_report.created_time}

            rows.append(row)

    return jsonify(**{'data': rows})


def get_conformance_report_by_user(db_session, username):
    """
    Returns the conformance report in descending order of creation date by user.
    """
    return db_session.query(ConformanceReport).filter(ConformanceReport.created_by == username).order_by(
        ConformanceReport.created_time.desc()).all()


@conformance.route('/api/batch_make_conform', methods=['POST'])
@login_required
def api_batch_make_conform():
    try:
        db_session = DBSession()

        report_id = request.form['report_id']
        hostnames = request.form.getlist('hostnames[]')
        install_actions = request.form.getlist('install_actions[]')
        scheduled_time = request.form['scheduled_time_UTC']
        server_id = request.form['server_id']
        server_directory = request.form['server_directory']
        custom_command_profile_ids = request.form.getlist('custom_command_profile_ids[]')

        conformance_report_entries = db_session.query(ConformanceReportEntry).\
            filter(ConformanceReportEntry.conformance_report_id == report_id).all()

        if len(conformance_report_entries) == 0:
            return jsonify({'status': 'The selected conformance report has no entries.'})

        if len(hostnames) == 0:
            return jsonify({'status': 'No host was selected during Make Conform.'})

        entry_dict = dict()
        for conformance_report_entry in conformance_report_entries:
            entry_dict[conformance_report_entry.hostname] = conformance_report_entry

        error_messages = []
        for hostname in hostnames:
            try:
                conformance_report_entry = entry_dict.get(hostname)
                if conformance_report_entry:
                    software_packages = conformance_report_entry.missing_packages.split(',')
                    host = get_host(db_session, hostname)

                    # The dependency on each install action is already indicated in the implicit ordering in the selector.
                    # If the user selected Pre-Upgrade and Install Add, Install Add (successor) will
                    # have Pre-Upgrade (predecessor) as the dependency.
                    dependency = 0
                    for install_action in install_actions:
                        new_install_job = create_or_update_install_job(db_session=db_session, host_id=host.id,
                                                                       install_action=install_action,
                                                                       scheduled_time=scheduled_time,
                                                                       software_packages=software_packages,
                                                                       server_id=server_id, server_directory=server_directory,
                                                                       custom_command_profile_ids=custom_command_profile_ids,
                                                                       dependency=dependency,
                                                                       created_by=current_user.username)
                        dependency = new_install_job.id
            except Exception as e:
                logger.exception('api_batch_make_conform() hit exception - hostname = {}.'.format(hostname))
                error_messages.append('Unable to create install job for host "' + hostname + '".')

        if len(error_messages) > 0:
            return jsonify({'status': '<br>'.join(error_messages)})

    except Exception as e:
        logger.exception('api_batch_make_conform() hit exception')
        return jsonify({'status': 'Failed - ' + e.message})

    return jsonify({'status': 'OK'})


@conformance.route('/api/make_conform', methods=['POST'])
@login_required
def api_make_conform():
    db_session = DBSession()

    hostname = request.form['hostname']
    install_actions = request.form.getlist('install_actions[]')
    scheduled_time = request.form['scheduled_time_UTC']
    software_packages = request.form['software_packages'].split()
    server_id = request.form['server_id']
    server_directory = request.form['server_directory']
    pending_downloads = request.form['pending_downloads'].split()
    custom_command_profile_ids = request.form.getlist('custom_command_profile_ids[]')

    host = get_host(db_session, hostname)

    try:
        # The dependency on each install action is already indicated in the implicit ordering in the selector.
        # If the user selected Pre-Upgrade and Install Add, Install Add (successor) will
        # have Pre-Upgrade (predecessor) as the dependency.
        dependency = 0
        for install_action in install_actions:
            new_install_job = create_or_update_install_job(db_session=db_session, host_id=host.id,
                                                           install_action=install_action,
                                                           scheduled_time=scheduled_time,
                                                           software_packages=software_packages,
                                                           server_id=server_id, server_directory=server_directory,
                                                           pending_downloads=pending_downloads,
                                                           custom_command_profile_ids=custom_command_profile_ids,
                                                           dependency=dependency,
                                                           created_by=current_user.username)
            dependency = new_install_job.id

        return jsonify({'status': 'OK'})
    except Exception as e:
        logger.exception('api_make_conform() hit exception')
        return jsonify({'status': 'Failed - ' + e.message})


@conformance.route('/export_software_profiles', methods=['POST'])
@login_required
def export_software_profiles():
    db_session = DBSession()

    software_profile_list = request.args.getlist('software_profile_list[]')[0].split(",")
    software_profiles = get_software_profile_list(db_session)
    d = {"CSM Server:Software Profile": {}}

    for software_profile in software_profiles:
        if software_profile.name in software_profile_list:
            d["CSM Server:Software Profile"][software_profile.name] = software_profile.packages

    temp_user_dir = create_temp_user_directory(current_user.username)
    software_profile_export_temp_path = os.path.normpath(os.path.join(temp_user_dir, "software_profile_export"))
    create_directory(software_profile_export_temp_path)
    make_file_writable(software_profile_export_temp_path)

    with open(os.path.join(software_profile_export_temp_path, 'software_profiles.json'), 'w') as command_export_file:
        command_export_file.write(json.dumps(d, indent=2))

    return send_file(os.path.join(software_profile_export_temp_path, 'software_profiles.json'), as_attachment=True)


@conformance.route('/api/assign_software_profile_to_hosts', methods=['POST'])
@login_required
def api_assign_software_profile_to_hosts():
    platform = request.form['platform']
    software_versions = request.form.getlist('software_versions[]')
    region_ids = request.form.getlist('region_ids[]')
    roles = request.form.getlist('roles[]')
    software_profile_id = int(request.form['software_profile_id'])

    db_session = DBSession()
    hosts = get_host_list_by(db_session, platform, software_versions, region_ids, roles)
    message = 'No host fits the selection criteria'
    if hosts:
        try:
            for host in hosts:
                host.software_profile_id = software_profile_id
            db_session.commit()
            message = ('%d hosts have been updated.' % len(hosts)) if len(hosts) > 1 else \
                ('%d host has been updated.' % len(hosts))
        except Exception as e:
            return jsonify({'status': e.message})

    return jsonify({'status': 'OK', 'message': message})


@conformance.route('/api/hosts/<hostname>/software_profile/delete', methods=['DELETE'])
@login_required
def api_remove_software_profile_for_host(hostname):
    if not can_create(current_user):
        abort(401)

    db_session = DBSession()
    host = get_host(db_session, hostname)
    if host:
        host.software_profile_id = None
        db_session.commit()
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ['json']


class SoftwareProfileForm(Form):
    software_profile_name = StringField('Software Profile Name', [required(), Length(max=30)])
    software_packages = TextAreaField('Software Packages', [required()])


class ConformanceForm(Form):
    conformance_reports = SelectField('Previously Run Reports', coerce=int, choices=[(-1, '')])


class AssignSoftwareProfileToHostsForm(Form):
    platform_2 = SelectField('Platform', coerce=str, choices=[('', '')])
    software_2 = SelectField('Software Version', coerce=str, choices=[('ALL', 'ALL')])
    region_2 = SelectField('Region', coerce=int, choices=[(-1, 'ALL')])
    role_2 = SelectField('Role', coerce=str, choices=[('ALL', 'ALL')])
    software_profile_2 = SelectField('Software Profile', coerce=str, choices=[(-1, '')])


class ViewHostSoftwareProfileForm(Form):
    software_profile_3 = SelectField('Software Profile', coerce=str, choices=[(-1, '')])


class ConformanceReportDialogForm(Form):
    software_profile = SelectField('Software Profile', coerce=str, choices=[(-1, '')])
    match_criteria = RadioField('Match Criteria',
                                choices=[('inactive', 'Software packages that are in inactive state'),
                                         ('active', 'Software packages that are in active state')], default='active')
    host_selection_criteria = RadioField('Host Selection Criteria',
                                         choices=[('auto', 'Select all hosts that match the selected software profile'),
                                                  ('manual', 'Select hosts manually')], default='manual')

    platform = SelectField('Platform', coerce=str, choices=[('', '')])
    software = SelectField('Software Version', coerce=str, choices=[('ALL', 'ALL')])
    region = SelectField('Region', coerce=int, choices=[(-1, 'ALL')])
    role = SelectField('Role', coerce=str, choices=[('ALL', 'ALL')])


class ExportConformanceReportForm(Form):
    include_host_packages = HiddenField("Include Host Packages on the Report")
    exclude_conforming_hosts = HiddenField("Exclude Conforming Hosts on the Report")


class MakeConformDialogForm(Form):
    install_action = SelectMultipleField('Install Action', coerce=str, choices=[('', '')])
    scheduled_time = StringField('Scheduled Time', [required()])
    scheduled_time_UTC = HiddenField('Scheduled Time')
    software_packages = TextAreaField('Software Packages')
    custom_command_profile = SelectMultipleField('Custom Command Profile', coerce=int, choices=[('', '')])


class BatchMakeConformDialogForm(Form):
    batch_install_action = SelectMultipleField('Install Action', coerce=str, choices=[('', '')])
    batch_scheduled_time = StringField('Scheduled Time', [required()])
    batch_scheduled_time_UTC = HiddenField('Scheduled Time')
    batch_custom_command_profile = SelectMultipleField('Custom Command Profile', coerce=int, choices=[('', '')])
