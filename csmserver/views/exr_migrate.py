import os
import subprocess
import requests

from constants import InstallAction, get_migration_directory, UserPrivilege

from common import can_edit_install
from common import create_or_update_install_job
from common import fill_custom_command_profiles
from common import fill_default_region
from common import fill_dependency_from_host_install_jobs
from common import fill_regions
from common import fill_servers
from common import get_first_install_action
from common import get_host
from common import get_host_list
from common import can_install
from common import get_return_url
from common import get_server_by_id

from database import DBSession
import datetime

from filters import get_datetime_string

from flask import Blueprint, jsonify, render_template, redirect, url_for, abort, request
from flask.ext.login import login_required, current_user

from models import Host, InstallJob, SystemOption

from wtforms import Form
from wtforms import TextField, SelectField, HiddenField, SelectMultipleField, StringField
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
    fill_dependencies_for_migration(form.dependency.choices)
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
                    custom_command_profile = ','.join([str(i) for i in form.custom_command_profile.data])

                    dependency = 0
                    # No dependency when it is 0 (a digit)
                    if not form.dependency.data.isdigit():
                        prerequisite_install_job = get_first_install_action(db_session, form.dependency.data)
                        if prerequisite_install_job is not None:
                            dependency = prerequisite_install_job.id

                    # If only one install_action, accept the selected dependency if any
                    if len(install_action) == 1:

                        new_install_job = create_or_update_install_job(db_session=db_session, host_id=host.id,
                                                                       install_action=install_action[0],
                                                                       scheduled_time=scheduled_time,
                                                                       software_packages=software_packages,
                                                                       server=server,
                                                                       server_directory=server_directory,
                                                                       best_effort_config=best_effort_config,
                                                                       config_filename=config_filename,
                                                                       custom_command_profile=custom_command_profile,
                                                                       dependency=dependency)
                        print("dependency for install_action = {} is {}".format(new_install_job.install_action,
                                                                                str(dependency)))
                    else:
                        # If a dependency was selected, that shall be the dependency for the first install action.
                        # If no dependency specified, the dependency for the first install action is 0.
                        # Then, the dependency for each install action is already indicated in the implicit
                        # ordering in the selector. If the user selected Pre-Upgrade and Install Add,
                        # Install Add (successor) will have Pre-Upgrade (predecessor) as the dependency.
                        for i in xrange(0, len(install_action)):
                            new_install_job = create_or_update_install_job(db_session=db_session, host_id=host.id,
                                                                           install_action=install_action[i],
                                                                           scheduled_time=scheduled_time,
                                                                           software_packages=software_packages,
                                                                           server=server,
                                                                           server_directory=server_directory,
                                                                           best_effort_config=best_effort_config,
                                                                           config_filename=config_filename,
                                                                           custom_command_profile=custom_command_profile,
                                                                           dependency=dependency)
                            print("dependency for install_action = {} is {}".format(install_action[i],
                                                                                    str(dependency)))
                            dependency = new_install_job.id

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

    # Retrieves all the install jobs for this host.  This will allow
    # the user to select which install job this install job can depend on.
    install_jobs = db_session.query(InstallJob).filter(InstallJob.host_id ==
                                                       host.id).order_by(InstallJob.scheduled_time.asc()).all()

    # Fills the selections
    fill_servers(form.server_dialog_server.choices, host.region.servers)
    fill_dependency_from_host_install_jobs(form.dependency.choices, install_jobs,
                                           (-1 if install_job is None else install_job.id))
    fill_custom_command_profiles(form.custom_command_profile.choices)

    if request.method == 'POST':
        if install_job is not None:
            # In Edit mode, the install_action UI on HostScheduleForm is disabled (not allow to change).
            # Thus, there will be no value returned by form.install_action.data.  So, re-use the existing ones.
            install_action = [ install_job.install_action ]
        else:
            install_action = form.install_action.data

        scheduled_time = form.scheduled_time_UTC.data
        software_packages = form.hidden_software_packages.data
        server = form.hidden_server.data
        server_directory = form.hidden_server_directory.data
        best_effort_config = form.hidden_best_effort_config.data
        config_filename = form.hidden_config_filename.data
        custom_command_profile = ','.join([str(i) for i in form.custom_command_profile.data])

        # install_action is a list object which can only contain one install action
        # at this time, accept the selected dependency if any
        dependency = int(form.dependency.data)
        create_or_update_install_job(db_session=db_session, host_id=host.id, install_action=install_action[0],
                                     scheduled_time=scheduled_time, software_packages=software_packages,
                                     server=server, server_directory=server_directory,
                                     best_effort_config=best_effort_config, config_filename=config_filename,
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

        # In Edit mode
        if install_job is not None:
            form.install_action.data = install_job.install_action

            form.hidden_best_effort_config.data = install_job.best_effort_config_applying
            form.hidden_config_filename.data = install_job.config_filename
            print "GET Edit install_job.config_filename = " + str(install_job.config_filename)

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

            print "Edit: the str(install_job.dependency) = " + str(install_job.dependency)
            form.dependency.data = str(install_job.dependency)

            if install_job.scheduled_time is not None:
                form.scheduled_time_UTC.data = \
                get_datetime_string(install_job.scheduled_time)

    return render_template('exr_migrate/schedule_migrate.html', form=form, system_option=SystemOption.get(db_session),
                           host=host, server_time=datetime.datetime.utcnow(), install_job=install_job,
                           return_url=return_url, install_action=get_install_migrations_dict())


@exr_migrate.route('/select_host.html')
def select_host():
    return render_template('exr_migrate/select_host.html')


@exr_migrate.route('/api/get_latest_config_migration_tool/')
@login_required
def get_latest_config_migration_tool():
    """Check if the latest NoX is in file. Download if not."""
    fileloc = get_migration_directory()

    (success, date) = get_nox_binary_publish_date()
    if not success:
        return jsonify( **{'data': [ { 'error': date } ] } )

    print("date from CCO = " + date)
    need_new_nox = False

    if os.path.isfile(fileloc + NOX_PUBLISH_DATE):
        try:
            with open(fileloc + NOX_PUBLISH_DATE, 'r') as f:
                current_date = f.readline()

            print("date on file = " + current_date)
            if date != current_date:
                need_new_nox = True
            f.close()
        except:
            return jsonify( **{'data': [ { 'error': 'Exception was thrown when reading file '
                                                    + fileloc + NOX_PUBLISH_DATE } ] } )

    else:
        need_new_nox = True

    print("need new nox = " + str(need_new_nox))

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


def fill_dependencies_for_migration(choices):
    # Remove all the existing entries
    del choices[:]
    choices.append((-1, 'None'))

    # The install action is listed in implicit ordering.  This ordering
    # is used to formulate the dependency.
    choices.append((InstallAction.PRE_MIGRATE, InstallAction.PRE_MIGRATE))
    choices.append((InstallAction.MIGRATE_SYSTEM, InstallAction.MIGRATE_SYSTEM))
    choices.append((InstallAction.POST_MIGRATE, InstallAction.POST_MIGRATE))


class ScheduleMigrationForm(Form):
    install_action = SelectMultipleField('Install Action', coerce=str, choices=[('', '')])

    scheduled_time = TextField('Scheduled Time', [required()])
    scheduled_time_UTC = HiddenField('Scheduled Time')
    custom_command_profile = SelectMultipleField('Custom Command Profile', coerce=int, choices=[(-1, '')])
    dependency = SelectField('Dependency', coerce=str, choices=[(-1, 'None')])

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
    # config_filename = StringField('Config Filename')
    # config_filename = SelectField('Config Filename', coerce=str, choices=[('', '')])
    hidden_config_filename = HiddenField('')

    hidden_edit = HiddenField('Edit')
