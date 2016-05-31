import os
import subprocess
import requests

from constants import InstallAction, get_migration_directory, UserPrivilege

from common import can_edit_install
from common import can_install
from common import create_or_update_install_job
from common import fill_custom_command_profiles
from common import fill_default_region
from common import fill_regions
from common import fill_servers
from common import get_last_install_action
from common import get_host
from common import get_host_list
from common import get_return_url
from common import get_server_by_id
from common import get_install_job_dependency_completed

from database import DBSession
import datetime

from filters import get_datetime_string

from flask import Blueprint, jsonify, render_template, redirect, url_for, abort, request
from flask.ext.login import login_required, current_user

from models import Host, InstallJob, SystemOption

from wtforms import Form
from wtforms import TextField, SelectField, HiddenField, SelectMultipleField
from wtforms.validators import required

from smu_info_loader import IOSXR_URL

NOX_64_BINARY = "nox-linux-64.bin"
# NOX_32_BINARY = "nox_linux_32bit_6.0.0v3.bin"
NOX_PUBLISH_DATE = "nox_linux.lastPublishDate"


exr_migrate = Blueprint('exr_migrate', __name__, url_prefix='/exr_migrate')


@exr_migrate.route('/schedule_migrate', methods=['GET', 'POST'])
@login_required
def schedule_migrate():
    # only operator and above can schedule migration
    if not can_install(current_user):
        render_template('user/not_authorized.html', user=current_user)

    db_session = DBSession()

    hosts = get_host_list(db_session)
    if hosts is None:
        abort(404)

    form = ScheduleMigrationForm(request.form)
    fill_regions(form.region.choices)
    fill_custom_command_profiles(form.custom_command_profile.choices)

    return_url = get_return_url(request, 'install_dashboard')

    if request.method == 'POST':

        # Retrieves from the multi-select box
        hostnames = form.hidden_hosts.data.split(',')

        install_action = form.install_action.data

        if hostnames is not None:
            print(str(form))
            print(str(form.data))
            print(str(hostnames))
            dependency_list = form.hidden_dependency.data.split(',')
            index = 0
            for hostname in hostnames:

                host = get_host(db_session, hostname)

                if host is not None:

                    db_session = DBSession()
                    scheduled_time = form.scheduled_time_UTC.data
                    software_packages = form.hidden_software_packages.data
                    server = form.hidden_server.data
                    server_directory = form.hidden_server_directory.data
                    best_effort_config = form.hidden_best_effort_config.data
                    config_filename = form.hidden_config_filename.data
                    override_hw_req = form.hidden_override_hw_req.data
                    custom_command_profile = ','.join([str(i) for i in form.custom_command_profile.data])

                    host.context[0].data['best_effort_config_applying'] = best_effort_config
                    host.context[0].data['config_filename'] = config_filename
                    host.context[0].data['override_hw_req'] = override_hw_req

                    # If the dependency is a previous job id, it's non-negative int string.
                    if int(dependency_list[index]) >= 0:
                        dependency = dependency_list[index]

                    # In this case, the dependency is '-1', which means no dependency for the first install action
                    else:
                        dependency = 0

                    # The dependency for the first install action depends on dependency_list[index].
                    # The dependency for each install action following first is indicated by the implicit
                    # ordering in the selector. If the user selected Pre-Migrate and Migrate,
                    # Migrate (successor) will have Pre-Migrate (predecessor) as the dependency.
                    for i in xrange(0, len(install_action)):
                        new_install_job = create_or_update_install_job(db_session=db_session, host_id=host.id,
                                                                       install_action=install_action[i],
                                                                       scheduled_time=scheduled_time,
                                                                       software_packages=software_packages,
                                                                       server=server,
                                                                       server_directory=server_directory,
                                                                       custom_command_profile=custom_command_profile,
                                                                       dependency=dependency)
                        print("dependency for install_action = {} is {}".format(install_action[i],
                                                                                str(dependency)))
                        dependency = new_install_job.id

                index += 1

        return redirect(url_for(return_url))
    else:
        # Initialize the hidden fields

        form.hidden_server_name.data = ''
        form.hidden_server.data = -1
        form.hidden_server_directory.data = ''
        form.hidden_pending_downloads.data = ''
        form.hidden_region.data = -1
        form.hidden_hosts.data = ''
        form.hidden_software_packages.data = ''
        form.hidden_edit.data = 'False'
        form.hidden_best_effort_config.data = '0'
        form.hidden_config_filename.data = ''
        form.hidden_override_hw_req.data = '0'
        form.hidden_dependency.data = ''

        return render_template('exr_migrate/schedule_migrate.html', form=form,
                               install_action=get_install_migrations_dict(), server_time=datetime.datetime.utcnow())


@exr_migrate.route('/hosts/<hostname>/schedule_install/<int:id>/edit/', methods=['GET', 'POST'])
@login_required
def host_schedule_install_migration_edit(hostname, id):
    # only operator and above can edit migration
    if not can_edit_install(current_user):
        abort(401)

    db_session = DBSession()

    install_job = db_session.query(InstallJob).filter(InstallJob.id == id).first()
    if install_job is None:
        abort(404)

    return handle_schedule_install_form(request=request, db_session=db_session,
                                        hostname=hostname, install_job=install_job)


def handle_schedule_install_form(request, db_session, hostname, install_job=None):
    host = get_host(db_session, hostname)
    if host is None:
        abort(404)

    if install_job is not None:

        print(str(install_job.install_action))

    return_url = get_return_url(request, 'host_dashboard')

    form = ScheduleMigrationForm(request.form)

    # Fills the selections
    fill_servers(form.server_dialog_server.choices, host.region.servers, include_local=False)
    fill_custom_command_profiles(form.custom_command_profile.choices)

    if request.method == 'POST':
        if install_job is not None:
            # In Edit mode, the install_action UI on HostScheduleForm is disabled (not allowed to change).
            # Thus, there will be no value returned by form.install_action.data.  So, re-use the existing ones.
            install_action = [ install_job.install_action ]
        else:
            install_action = form.install_action.data

        scheduled_time = form.scheduled_time_UTC.data
        software_packages = form.hidden_software_packages.data
        server = form.hidden_server.data
        server_directory = form.hidden_server_directory.data
        best_effort_config = form.hidden_best_effort_config.data
        override_hw_req = form.hidden_override_hw_req.data
        config_filename = form.hidden_config_filename.data
        custom_command_profile = ','.join([str(i) for i in form.custom_command_profile.data])

        host.context[0].data['best_effort_config_applying'] = best_effort_config
        host.context[0].data['config_filename'] = config_filename
        host.context[0].data['override_hw_req'] = override_hw_req

        # install_action is a list object which can only contain one install action
        # at this editing time, accept the selected dependency if any

        dependency = int(form.hidden_dependency.data)
        create_or_update_install_job(db_session=db_session, host_id=host.id, install_action=install_action[0],
                                     scheduled_time=scheduled_time, software_packages=software_packages,
                                     server=server, server_directory=server_directory,
                                     custom_command_profile=custom_command_profile, dependency=dependency,
                                     install_job=install_job)

        return redirect(url_for(return_url, hostname=hostname))

    elif request.method == 'GET':
        # Initialize the hidden fields
        form.hidden_server.data = -1
        form.hidden_server_name.data = ''
        form.hidden_server_directory.data = ''
        form.hidden_pending_downloads.data = ''
        form.hidden_edit.data = install_job is not None

        form.hidden_region.data = str(host.region.name)
        fill_default_region(form.region.choices, host.region)
        form.hidden_hosts.data = hostname
        form.hidden_dependency.data = ''

        # In Edit mode
        if install_job is not None:
            form.install_action.data = install_job.install_action

            if install_job.custom_command_profile_id:
                ids = [int(id) for id in install_job.custom_command_profile_id.split(',')]
                form.custom_command_profile.data = ids

            form.hidden_best_effort_config.data = host.context[0].data.get('best_effort_config_applying')
            form.hidden_override_hw_req.data = host.context[0].data['override_hw_req']
            form.hidden_config_filename.data = host.context[0].data.get('config_filename')

            if install_job.server_id is not None:
                form.hidden_server.data = install_job.server_id
                server = get_server_by_id(db_session, install_job.server_id)
                if server is not None:
                    form.hidden_server_name.data = server.hostname

                form.hidden_server_directory.data = '' if install_job.server_directory is None \
                    else install_job.server_directory

            form.hidden_pending_downloads.data = '' if install_job.pending_downloads is None \
                else install_job.pending_downloads

            # Form a line separated list for the textarea
            if install_job.packages is not None:

                form.hidden_software_packages.data = install_job.packages

            if install_job.dependency is not None:
                form.hidden_dependency.data = str(install_job.dependency)
            else:
                form.hidden_dependency.data = '-1'

            if install_job.scheduled_time is not None:
                form.scheduled_time_UTC.data = \
                get_datetime_string(install_job.scheduled_time)

    return render_template('exr_migrate/schedule_migrate.html', form=form, system_option=SystemOption.get(db_session),
                           host=host, server_time=datetime.datetime.utcnow(), install_job=install_job,
                           return_url=return_url, install_action=get_install_migrations_dict())


@exr_migrate.route('/select_host.html')
def select_host():
    return render_template('exr_migrate/select_host.html')

@exr_migrate.route('/api/get_dependencies/')
@login_required
def get_dependencies():
    db_session = DBSession()
    hostnames = request.args.get('hosts', '', type=str).split(',')
    dependency = request.args.get('dependency', '', type=str)

    dependency_list = []
    disqualified_count = 0
    for hostname in hostnames:
        host = get_host(db_session, hostname)

        if host and host.connection_param[0] and (not host.connection_param[0].port_number):
            disqualified_count += 1
            dependency_list.append('-2')
            continue

        if dependency:
            prerequisite_install_job = get_last_install_action(db_session, dependency, get_host(db_session, hostname).id)
            if prerequisite_install_job is not None:
                dependency_list.append(prerequisite_install_job.id)
            else:
                num_completed_jobs = get_install_job_dependency_completed(db_session, dependency, host.id)
                if len(num_completed_jobs) > 0:
                    dependency_list.append('-1')
                else:
                    disqualified_count += 1
                    dependency_list.append('-2')
        else:
            dependency_list.append('-1')

    return jsonify(**{'data': [{ 'dependency_list': dependency_list, 'disqualified_count' :  disqualified_count} ] } )


@exr_migrate.route('/api/get_latest_config_migration_tool/')
@login_required
def get_latest_config_migration_tool():
    """Check if the latest NoX is in file. Download if not."""
    fileloc = get_migration_directory()

    (success, date) = get_nox_binary_publish_date()
    if not success:
        return jsonify( **{'data': [ { 'error': date } ] } )

    need_new_nox = False

    if os.path.isfile(fileloc + NOX_PUBLISH_DATE):
        try:
            with open(fileloc + NOX_PUBLISH_DATE, 'r') as f:
                current_date = f.readline()

            if date != current_date:
                need_new_nox = True
            f.close()
        except:
            return jsonify( **{'data': [ { 'error': 'Exception was thrown when reading file '
                                                    + fileloc + NOX_PUBLISH_DATE } ] } )

    else:
        need_new_nox = True

    if need_new_nox:

        check_32_or_64_system = subprocess.Popen(['uname', '-a'], stdout=subprocess.PIPE)
        out, err = check_32_or_64_system.communicate()
        if err:
            return jsonify( **{'data': [ { 'error': 'Error when trying to determine whether the \
                                                    linux system that you are hosting CSM on is \
                                                    32 bit or 64 bit with command "uname -a".' } ] } )

        if "x86_64" in out:
            nox_to_use = NOX_64_BINARY
        else:
            return jsonify( **{'data': [ { 'error': 'NoX is not available for 32 bit linux.' } ] } )
            # nox_to_use = NOX_32_BINARY

        (success, error_msg) = get_file_http(nox_to_use, fileloc)
        if not success:
            return jsonify( **{'data': [ { 'error': error_msg } ] } )

        try:
            with open(fileloc + NOX_PUBLISH_DATE, 'w') as nox_publish_date_file:
                nox_publish_date_file.write(date)
            nox_publish_date_file.close()
        except:
            nox_publish_date_file.close()
            return jsonify( **{'data': [ { 'error': 'Exception was thrown when writing file ' +
                                                    fileloc + NOX_PUBLISH_DATE } ] } )

    return jsonify( **{'data': [ { 'error': 'None' } ] } )


def get_nox_binary_publish_date():
    """Get the text file with the lastest publish date of NoX"""
    try:
        url = IOSXR_URL + "/" + NOX_PUBLISH_DATE
        r = requests.get(url)
        if not r.ok:
            return 0, 'HTTP request to get ' + IOSXR_URL + '/' + NOX_PUBLISH_DATE + ' failed.'
        return (1, r.text)
    except:

        return 0, 'Exception was thrown during HTTP request to get ' + IOSXR_URL + '/' + NOX_PUBLISH_DATE


def get_file_http(filename, destination):
    """Download file through HTTP"""
    try:
        with open(destination + filename, 'wb') as handle:
            response = requests.get(IOSXR_URL + "/" + filename, stream=True)

            if not response.ok:
                return 0, 'HTTP request to get ' + IOSXR_URL + '/' + filename + ' failed.'

            for block in response.iter_content(1024):
                handle.write(block)
        handle.close()
    except:
        handle.close()
        return (0, 'Exception was thrown during HTTP request to get ' + IOSXR_URL + '/' + filename +
                   ' and writing it to ' + destination + '.')

    return 1, ''


def get_install_migrations_dict():
    return {
        "premigrate": InstallAction.PRE_MIGRATE,
        "migrate": InstallAction.MIGRATE_SYSTEM,
        "postmigrate": InstallAction.POST_MIGRATE,
        "allformigrate": InstallAction.ALL_FOR_MIGRATE
    }


class ScheduleMigrationForm(Form):
    install_action = SelectMultipleField('Install Action', coerce=str, choices=[('', '')])

    scheduled_time = TextField('Scheduled Time', [required()])
    scheduled_time_UTC = HiddenField('Scheduled Time')
    custom_command_profile = SelectMultipleField('Custom Command Profile', coerce=int, choices=[(-1, '')])

    region = SelectField('Region', coerce=int, choices=[(-1, '')])
    role = SelectField('Role', coerce=str, choices=[('Any', 'Any')])
    software = SelectField('Software Version', coerce=str, choices=[('Any', 'Any')])

    server_dialog_target_software = TextField('Target Software Release')
    server_dialog_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])
    server_dialog_server_directory = SelectField('Server Directory', coerce=str, choices=[('', '')])

    hidden_region = HiddenField('')
    hidden_hosts = HiddenField('')

    hidden_server = HiddenField('')
    hidden_server_name = HiddenField('')
    hidden_server_directory = HiddenField('')
    hidden_pending_downloads = HiddenField('Pending Downloads')
    hidden_software_packages = HiddenField('')

    hidden_best_effort_config = HiddenField('')
    hidden_override_hw_req = HiddenField('')
    hidden_config_filename = HiddenField('')

    hidden_edit = HiddenField('Edit')

    hidden_dependency = HiddenField('')
