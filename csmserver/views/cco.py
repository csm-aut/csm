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
from flask import abort
from flask import render_template
from flask import request
from flask import jsonify
from flask import redirect
from flask import url_for
from flask import send_file

from flask.ext.login import login_required
from flask.ext.login import current_user

from wtforms import Form
from wtforms import StringField
from wtforms import PasswordField
from wtforms import SelectField

from database import DBSession

from models import SystemOption
from models import SMUMeta
from models import logger
from models import SMUInfo
from models import Preferences

from common import get_host
from common import get_user_by_id
from common import get_server_list
from common import fill_servers
from common import get_host_active_packages
from common import create_download_jobs
from common import can_check_reachability

from forms import ServerDialogForm
from forms import SoftwareProfileForm
from forms import ExportInformationForm
from forms import BrowseServerDialogForm

from constants import UNKNOWN
from constants import PlatformFamily
from constants import BUG_SEARCH_URL
from constants import get_repository_directory
from constants import ExportInformationFormat
from constants import ExportSoftwareInformationLayout

from filters import beautify_platform
from filters import time_difference_UTC
from filters import get_datetime_string

from smu_info_loader import SMUInfoLoader

from utils import is_empty
from utils import get_file_list
from utils import get_json_value
from utils import get_software_platform
from utils import comma_delimited_str_to_list

from report_writer import ExportSoftwareInfoHTMLConciseWriter
from report_writer import ExportSoftwareInfoHTMLDefaultWriter
from report_writer import ExportSoftwareInfoExcelConciseWriter
from report_writer import ExportSoftwareInfoExcelDefaultWriter

from smu_utils import SMU_INDICATOR
from smu_utils import get_optimized_list

from cisco_service.bug_service import BugServiceHandler
from cisco_service.bsd_service import BSDServiceHandler

cco = Blueprint('cco', __name__, url_prefix='/cco')


@cco.route('/platform/<platform>/release/<release>')
@login_required
def home(platform, release):
    system_option = SystemOption.get(DBSession())
    form = BrowseServerDialogForm(request.form)
    fill_servers(form.dialog_server.choices, get_server_list(DBSession()), False)
    export_software_information_form = ExportSoftwareInformationForm(request.form)

    return render_template('cco/home.html', form=form, platform=platform,
                           release=release, system_option=system_option,
                           export_software_information_form=export_software_information_form)


@cco.route('/api/get_cco_retrieval_elapsed_time/platform/<platform>/release/<release>')
@login_required
def api_get_cco_retrieval_elapsed_time(platform, release):
    smu_meta = DBSession().query(SMUMeta).filter(SMUMeta.platform_release == platform + '_' + release).first()

    retrieval_elapsed_time = UNKNOWN
    if smu_meta is not None:
        retrieval_elapsed_time = time_difference_UTC(smu_meta.retrieval_time)

    return jsonify(**{'data': [{'retrieval_elapsed_time': retrieval_elapsed_time}]})


@cco.route('/api/create_download_jobs', methods=['POST'])
@login_required
def api_create_download_jobs():
    try:
        server_id = request.form.get("server_id")
        server_directory = request.form.get("server_directory")
        smu_list = request.form.get("smu_list").split()
        pending_downloads = request.form.get("pending_downloads").split()

        # Derives the platform and release using the first SMU name.
        if len(smu_list) > 0 and len(pending_downloads) > 0:
            platform, release = SMUInfoLoader.get_platform_and_release(smu_list)

            create_download_jobs(DBSession(), platform, release, pending_downloads, server_id, server_directory, current_user.username)
        return jsonify({'status': 'OK'})
    except:
        logger.exception('api_create_download_jobs() hit exception')
        return jsonify({'status': 'Failed'})


@cco.route('/api/get_smu_details/smu_id/<smu_id>')
@login_required
def api_get_smu_details(smu_id):
    rows = []
    db_session = DBSession()

    smu_info = db_session.query(SMUInfo).filter(SMUInfo.id == smu_id).first()
    if smu_info is not None:
        row = dict()
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
        row['prerequisites_smu_ids'] = get_smu_ids(db_session, smu_info.prerequisites)
        row['supersedes_smu_ids'] = get_smu_ids(db_session, smu_info.supersedes)
        row['superseded_by_smu_ids'] = get_smu_ids(db_session, smu_info.superseded_by)

        rows.append(row)

    return jsonify(**{'data': rows})


def get_smu_ids(db_session, smu_name_list):
    smu_ids = []
    smu_names = comma_delimited_str_to_list(smu_name_list)
    for smu_name in smu_names:
        smu_info = db_session.query(SMUInfo).filter(SMUInfo.name == smu_name).first()
        if smu_info is not None:
            smu_ids.append(smu_info.id)
        else:
            smu_ids.append(UNKNOWN)

    return ','.join([id for id in smu_ids])


@cco.route('/api/get_ddts_details/ddts_id/<ddts_id>')
@login_required
def api_get_ddts_details(ddts_id):
    username = Preferences.get(DBSession(), current_user.id).cco_username
    password = Preferences.get(DBSession(), current_user.id).cco_password
    bsh = BugServiceHandler(username, password, ddts_id)
    try:
        bug_info = bsh.get_bug_info()
    except Exception as e:
        logger.exception('api_get_ddts_details() hit exception ' + e.message)
        if e.message == 'access_token':
            error_msg = 'Could not retrieve bug information.  The username and password defined may not be correct ' \
                        '(Check Tools - User Preferences)'
        else:
            error_msg = 'Could not retrieve bug information.'
        return jsonify(**{'data': {'ErrorMsg': error_msg}})

    info = {}

    statuses = {'O': 'Open',
                'F': 'Fixed',
                'T': 'Terminated'}

    severities = {'1': "1 Catastrophic",
                  '2': "2 Severe",
                  '3': "3 Moderate",
                  '4': "4 Minor",
                  '5': "5 Cosmetic",
                  '6': "6 Enhancement"}

    info['status'] = statuses[get_json_value(bug_info, 'status')] \
        if get_json_value(bug_info, 'status') in statuses else get_json_value(bug_info, 'status')
    info['product'] = get_json_value(bug_info, 'product')
    info['severity'] = severities[get_json_value(bug_info, 'severity')] \
        if get_json_value(bug_info, 'severity') in severities else get_json_value(bug_info, 'severity')
    info['headline'] = get_json_value(bug_info, 'headline')
    info['support_case_count'] = get_json_value(bug_info, 'support_case_count')
    info['last_modified_date'] = get_json_value(bug_info, 'last_modified_date')
    info['bug_id'] = get_json_value(bug_info, 'bug_id')
    info['created_date'] = get_json_value(bug_info, 'created_date')
    info['duplicate_of'] = get_json_value(bug_info, 'duplicate_of')
    info['description'] = get_json_value(bug_info, 'description').replace('\n', '<br>') \
        if get_json_value(bug_info, 'description') else None
    info['known_affected_releases'] = get_json_value(bug_info, 'known_affected_releases').replace(' ', '<br>') \
        if get_json_value(bug_info, 'known_affected_releases') else None
    info['known_fixed_releases'] = get_json_value(bug_info, 'known_fixed_releases').replace(' ', '<br>') \
        if get_json_value(bug_info, 'known_fixed_releases') else None
    info['ErrorDescription'] = get_json_value(bug_info, 'ErrorDescription')
    info['SuggestedAction'] = get_json_value(bug_info, 'SuggestedAction')

    return jsonify(**{'data': info})


@cco.route('/user_preferences', methods=['GET','POST'])
@login_required
def user_preferences():
    db_session = DBSession()
    form = PreferencesForm(request.form)

    user = get_user_by_id(db_session, current_user.id)

    if request.method == 'POST' and form.validate():
        user.preferences[0].cco_username = form.cco_username.data

        if len(form.cco_password.data) > 0:
            user.preferences[0].cco_password = form.cco_password.data

        # All the checked checkboxes (i.e. platforms and releases to exclude).
        values = request.form.getlist('check')
        excluded_platform_list = ','.join(values)

        preferences = Preferences.get(db_session, current_user.id)
        preferences.excluded_platforms_and_releases = excluded_platform_list

        db_session.commit()

        return redirect(url_for('home'))
    else:
        preferences = user.preferences[0]
        form.cco_username.data = preferences.cco_username

        if not is_empty(user.preferences[0].cco_password):
            form.password_placeholder = 'Use Password on File'
        else:
            form.password_placeholder = 'No Password Specified'

    return render_template('cco/preferences.html', form=form,
                           platforms_and_releases=get_platforms_and_releases_dict(db_session))


def get_platforms_and_releases_dict(db_session):
    excluded_platform_list = []
    preferences = Preferences.get(db_session, current_user.id)

    # It is possible that the preferences have not been created yet.
    if preferences is not None and preferences.excluded_platforms_and_releases is not None:
        excluded_platform_list = preferences.excluded_platforms_and_releases.split(',')

    rows = []
    catalog = SMUInfoLoader.get_catalog()
    if len(catalog) > 0:
        for platform in catalog:
            releases = catalog[platform]
            for release in releases:
                row = dict()
                row['platform'] = platform
                row['release'] = release
                row['excluded'] = True if platform + '_' + release in excluded_platform_list else False
                rows.append(row)
    else:
        # If get_catalog() failed, populate the excluded platforms and releases
        for platform_and_release in excluded_platform_list:
            pos = platform_and_release.rfind('_')
            if pos > 0:
                row = dict()
                row['platform'] = platform_and_release[:pos]
                row['release'] = platform_and_release[pos+1:]
                row['excluded'] = True
                rows.append(row)

    return rows


@cco.route('/software/export/platform/<platform>/release/<release>', methods=['POST'])
@login_required
def export_software_information(platform, release):
    smu_loader = SMUInfoLoader(platform, release)
    if not smu_loader.is_valid:
        return jsonify({'status': 'Failed'})

    export_format = request.args.get('export_format')
    export_layout = request.args.get('export_layout')
    export_filter = request.args.get('filter')

    if export_filter == 'Optimal':
        smu_list = smu_loader.get_optimal_smu_list()
        sp_list = smu_loader.get_optimal_sp_list()
    else:
        smu_list = smu_loader.get_smu_list()
        sp_list = smu_loader.get_sp_list()

    if export_format == ExportInformationFormat.HTML:
        if export_layout == ExportSoftwareInformationLayout.CONCISE:
            writer = ExportSoftwareInfoHTMLConciseWriter(user=current_user, smu_loader=smu_loader,
                                                         smu_list=smu_list, sp_list=sp_list)
        else:
            writer = ExportSoftwareInfoHTMLDefaultWriter(user=current_user, smu_loader=smu_loader,
                                                         smu_list=smu_list, sp_list=sp_list)
    else:
        if export_layout == ExportSoftwareInformationLayout.CONCISE:
            writer = ExportSoftwareInfoExcelConciseWriter(user=current_user, smu_loader=smu_loader,
                                                          smu_list=smu_list, sp_list=sp_list)
        else:
            writer = ExportSoftwareInfoExcelDefaultWriter(user=current_user, smu_loader=smu_loader,
                                                          smu_list=smu_list, sp_list=sp_list)

    return send_file(writer.write_report(), as_attachment=True)


@cco.route('/api/check_cisco_authentication/', methods=['POST'])
@login_required
def check_cisco_authentication():
    preferences = Preferences.get(DBSession(), current_user.id)
    if preferences is not None:
        if not is_empty(preferences.cco_username) and not is_empty(preferences.cco_password):
            return jsonify({'status': 'OK'})

    return jsonify({'status': 'Failed'})


@cco.route('/optimize_software')
@login_required
def optimize_software():
    server_dialog_form = ServerDialogForm(request.form)
    software_profile_form = SoftwareProfileForm(request.form)

    return render_template('cco/optimize_software.html',
                           server_dialog_form=server_dialog_form,
                           software_profile_form=software_profile_form,
                           system_option=SystemOption.get(DBSession()))


def get_filtered_platform_list(platform, releases, excluded_platform_list):
    result_list = []
    for release in releases:
        if platform + '_' + release not in excluded_platform_list:
            result_list.append(release)

    return result_list


@cco.route('/api/get_catalog')
@login_required
def api_get_catalog():
    db_session = DBSession()
    excluded_platform_list = []

    preferences = Preferences.get(db_session, current_user.id)
    if preferences.excluded_platforms_and_releases is not None:
        excluded_platform_list = preferences.excluded_platforms_and_releases.split(',')

    rows = []

    catalog = SMUInfoLoader.get_catalog()
    for platform in catalog:
        releases = get_filtered_platform_list(platform, catalog[platform], excluded_platform_list)
        if len(releases) > 0:
            row = dict()
            row['platform'] = platform
            row['beautified_platform'] = beautify_platform(platform)
            row['releases'] = releases
            rows.append(row)

    return jsonify(**{'data': rows})


@cco.route('/api_fetch_cco_software/platform/<platform>/release/<release>')
@login_required
def api_fetch_cco_software(platform, release):
    smu_loader = SMUInfoLoader(platform, release)
    return jsonify({'status': 'OK' if smu_loader.is_valid else 'Failed'})


@cco.route('/api/get_smu_list/platform/<platform>/release/<release>')
@login_required
def api_get_smu_list(platform, release):
    smu_loader = SMUInfoLoader(platform, release, from_cco=False)
    if not smu_loader.is_valid:
        return jsonify(**{'data': []})

    hostname = request.args.get('hostname')
    hide_installed_packages = request.args.get('hide_installed_packages')

    if request.args.get('filter') == 'Optimal':
        return get_smu_or_sp_list(hostname, hide_installed_packages,
                                  smu_loader.get_optimal_smu_list(), smu_loader.file_suffix)
    else:
        return get_smu_or_sp_list(hostname, hide_installed_packages,
                                  smu_loader.get_smu_list(), smu_loader.file_suffix)


@cco.route('/api/get_sp_list/platform/<platform>/release/<release>')
@login_required
def api_get_sp_list(platform, release):
    smu_loader = SMUInfoLoader(platform, release, from_cco=False)
    if not smu_loader.is_valid:
        return jsonify(**{'data': []})

    hostname = request.args.get('hostname')
    hide_installed_packages = request.args.get('hide_installed_packages')

    if request.args.get('filter') == 'Optimal':
        return get_smu_or_sp_list(hostname, hide_installed_packages,
                                  smu_loader.get_optimal_sp_list(), smu_loader.file_suffix)
    else:
        return get_smu_or_sp_list(hostname, hide_installed_packages,
                                  smu_loader.get_sp_list(), smu_loader.file_suffix)


@cco.route('/api/get_tar_list/platform/<platform>/release/<release>')
@login_required
def api_get_tar_list(platform, release):
    smu_loader = SMUInfoLoader(platform, release, from_cco=False)

    if not smu_loader.is_valid:
        return jsonify(**{'data': []})
    else:
        file_list = get_file_list(get_repository_directory(), '.tar')
        tars_list = smu_loader.get_tar_list()
        rows = []
        for tar_info in tars_list:
            row = dict()
            row['ST'] = 'True' if tar_info.name in file_list else 'False'
            row['name'] = tar_info.name
            row['compressed_size'] = tar_info.compressed_image_size
            row['description'] = ""
            rows.append(row)

    return jsonify(**{'data': rows})


def get_smu_or_sp_list(hostname, hide_installed_packages, smu_info_list, file_suffix):
    """
    Return the SMU/SP list.  If hostname is given, compare its active packages.
    """
    file_list = get_file_list(get_repository_directory(), '.' + file_suffix)

    host_packages = [] if is_empty(hostname) else get_host_active_packages(hostname)

    check_package_bundles = False

    if not is_empty(hostname):
        db_session = DBSession()
        host = get_host(db_session, hostname)

        if host is not None:
            software_platform = get_software_platform(host.family, host.os_type)

            # Only for ASR9K, other platforms do not follow the definition of package_bundles
            # (i.e., the values values in the package_bundles cannot be used to compare with
            # the package list on the device).
            if software_platform == PlatformFamily.ASR9K:
                check_package_bundles = True

    rows = []
    for smu_info in smu_info_list:

        # Verify if the package has already been installed.
        installed = False
        for host_package in host_packages:
            if smu_info.name in host_package:
                installed = True
                break

        include = False if (hide_installed_packages == 'true' and installed) else True
        if include:
            row = dict()
            row['ST'] = 'True' if smu_info.name + '.' + file_suffix in file_list else 'False'
            row['package_name'] = smu_info.name + '.' + file_suffix
            row['posted_date'] = smu_info.posted_date.split()[0]
            row['ddts'] = smu_info.ddts
            row['ddts_url'] = BUG_SEARCH_URL + smu_info.ddts
            row['type'] = smu_info.type
            row['description'] = smu_info.description
            row['impact'] = smu_info.impact
            row['functional_areas'] = smu_info.functional_areas
            row['id'] = smu_info.id
            row['name'] = smu_info.name
            row['status'] = smu_info.status
            row['package_bundles'] = smu_info.package_bundles
            row['compressed_image_size'] = smu_info.compressed_image_size
            row['uncompressed_image_size'] = smu_info.uncompressed_image_size
            row['is_installed'] = installed

            row['is_applicable'] = True

            if check_package_bundles and SMU_INDICATOR in smu_info.name:
                row['is_applicable'] = is_smu_applicable(host_packages, smu_info.package_bundles)

            rows.append(row)

    return jsonify(**{'data': rows})


def is_smu_applicable(host_packages, required_package_bundles):
    """
    Only SMU should go through this logic
    The package_bundles defined must be satisfied for the SMU to be applicable.
    However,asr9k-fpd-px can be excluded.
    """
    if not is_empty(required_package_bundles):
        package_bundles = required_package_bundles.split(',')
        package_bundles = [p for p in package_bundles if p != 'asr9k-fpd-px']

        count = 0
        for package_bundle in package_bundles:
            for host_package in host_packages:
                if package_bundle in host_package:
                    count += 1
                    break

        if count != len(package_bundles):
            return False

    return True


@cco.route('/api/optimize_software')
@login_required
def api_optimize_software():
    smu_list = request.args.get('smu_list').split()
    return jsonify(**{'data': get_optimized_list(smu_list)})


@cco.route('/api/validate_cisco_user', methods=['POST'])
@login_required
def validate_cisco_user():
    if not can_check_reachability(current_user):
        abort(401)

    try:
        username = request.form['username']
        password = request.form['password']

        if len(password) == 0:
            password = Preferences.get(DBSession(), current_user.id).cco_password

        BSDServiceHandler.get_access_token(username, password)
        return jsonify({'status': 'OK'})
    except KeyError:
        return jsonify({'status': 'Failed'})
    except:
        logger.exception('validate_cisco_user() hit exception')
        return jsonify({'status': 'Failed'})


@cco.route('/api/refresh_all_smu_info')
@login_required
def api_refresh_all_smu_info():
    if SMUInfoLoader.refresh_all():
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'status': 'Failed'})


@cco.route('/api/get_cco_lookup_time')
@login_required
def api_get_cco_lookup_time():
    system_option = SystemOption.get(DBSession())
    if system_option.cco_lookup_time is not None:
        return jsonify(**{'data': [{'cco_lookup_time': get_datetime_string(system_option.cco_lookup_time)}]})
    else:
        return jsonify({'status': 'Failed'})


class PreferencesForm(Form):
    cco_username = StringField('Username')
    cco_password = PasswordField('Password')


class ExportSoftwareInformationForm(ExportInformationForm):
    export_layout = SelectField('Layout', coerce=str,
                                choices=[(ExportSoftwareInformationLayout.CONCISE,
                                          ExportSoftwareInformationLayout.CONCISE),
                                         (ExportSoftwareInformationLayout.DEFAULT,
                                          ExportSoftwareInformationLayout.DEFAULT)])