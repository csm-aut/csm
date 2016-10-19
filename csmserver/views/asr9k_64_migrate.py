import os
import subprocess
import requests
import json
import csv

from constants import InstallAction, get_migration_directory, ServerType

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
from common import get_server_list
from common import get_last_unfinished_install_action
from common import get_last_completed_or_failed_install_action

from database import DBSession
import datetime

from filters import get_datetime_string

from flask import Blueprint, jsonify, render_template, redirect, url_for, abort, request
from flask.ext.login import login_required, current_user
from flask import flash
from flask import send_from_directory
from werkzeug.utils import secure_filename

from models import InstallJob, SystemOption, ConvertConfigJob, JobStatus
from models import logger

from wtforms import Form
from wtforms import StringField, SelectField, HiddenField, SelectMultipleField
from wtforms.validators import required

from smu_info_loader import IOSXR_URL

from utils import create_temp_user_directory, create_directory

from server_helper import TFTPServer, FTPServer, SFTPServer


NOX_64_BINARY = "nox-linux-64.bin"

# NOX_32_BINARY = "nox_linux_32bit_6.0.0v3.bin"
NOX_PUBLISH_DATE = "nox_linux.lastPublishDate"

asr9k_64_migrate = Blueprint('asr9k_64_migrate', __name__, url_prefix='/asr9k_64_migrate')


def get_config_conversion_path():
    temp_user_dir = create_temp_user_directory(current_user.username)
    config_conversion_path = os.path.normpath(os.path.join(temp_user_dir, "config_conversion"))
    create_directory(config_conversion_path)
    return config_conversion_path


def convert_config(db_session, http_request, template, schedule_form):

    config_form = init_config_form(db_session, http_request, get=True)

    success, err_msg = download_latest_config_migration_tool()
    if not success:
        return render_template(template, config_form=config_form,
                               input_filename="", err_msg=err_msg, schedule_form=schedule_form,
                               install_action=get_install_migrations_dict(),
                               server_time=datetime.datetime.utcnow())

    # check if the post request has the file part
    if 'file' not in http_request.files:
        flash('No file in request.')
        return render_template(template, config_form=config_form,
                               input_filename="", err_msg="Internal error - No file.",
                               schedule_form=schedule_form,
                               install_action=get_install_migrations_dict(),
                               server_time=datetime.datetime.utcnow(),)

    input_file = http_request.files['file']
    # if user does not select file, browser also
    # submit a empty part without filename
    if input_file.filename == '':
        flash('No selected file.')
        return render_template(template, config_form=config_form,
                               input_filename="", err_msg="Internal error - No selected file.",
                               schedule_form=schedule_form,
                               install_action=get_install_migrations_dict(),
                               server_time=datetime.datetime.utcnow(),)

    config_conversion_path = get_config_conversion_path()
    create_directory(config_conversion_path)

    if input_file:
        filename = secure_filename(input_file.filename)
        input_file.save(os.path.join(config_conversion_path, filename))

    return render_template(template, config_form=config_form,
                           input_filename=input_file.filename, err_msg="", schedule_form=schedule_form,
                           install_action=get_install_migrations_dict(),
                           server_time=datetime.datetime.utcnow())


@asr9k_64_migrate.route('/api/convert_config_file')
@login_required
def convert_config_file():
    filename = request.args.get('filename', '', type=str)

    filename = secure_filename(filename)

    config_conversion_path = get_config_conversion_path()

    db_session = DBSession()

    convert_config_job = ConvertConfigJob(file_path=os.path.join(config_conversion_path, filename),
                                          status='Preparing the conversion')
    db_session.add(convert_config_job)
    db_session.commit()

    job_id = convert_config_job.id

    return jsonify({'status': 'OK', 'job_id': job_id})


@asr9k_64_migrate.route('/api/get_config_conversion_progress')
@login_required
def get_config_conversion_progress():

    job_id = request.args.get('job_id', 0, type=int)

    db_session = DBSession()

    convert_config_job = db_session.query(ConvertConfigJob).filter(ConvertConfigJob.id == job_id).first()
    if convert_config_job is None:
        logger.error('Unable to retrieve Convert Config Job: %s' % job_id)
        return jsonify(status='Unable to retrieve job')
    return jsonify(status='OK', progress=convert_config_job.status)


@asr9k_64_migrate.route('/api/get_file')
@login_required
def get_file():
    which_file = request.args.get('file_number', 0, type=int)

    filename = request.args.get('filename', '', type=str)

    config_conversion_path = get_config_conversion_path()

    stripped_filename = get_stripped_filename(filename)

    output_html = stripped_filename + ".html"
    output_iox = stripped_filename + ".iox"
    output_cal = stripped_filename + ".cal"

    if which_file == 1:
        return send_from_directory(config_conversion_path,
                                   output_html, cache_timeout=0)
    elif which_file == 2:
        return send_from_directory(config_conversion_path,
                                   output_iox, cache_timeout=0)
    elif which_file == 3:
        return send_from_directory(config_conversion_path,
                                   output_cal, cache_timeout=0)

    return jsonify(**{'data': 'file does not exist.'})


@asr9k_64_migrate.route('/api/get_analysis')
@login_required
def process_config_conversion_output():
    filename = request.args.get('filename', '', type=str)

    config_conversion_path = get_config_conversion_path()

    stripped_filename = get_stripped_filename(filename)

    output_csv = stripped_filename + ".csv"
    html_file = stripped_filename + ".html"

    map_csv_category_to_final_category = {
        'KNOWN_SUPPORTED': 'supported',
        'KNOWN_UNSUPPORTED': 'unsupported',
        'UNKNOWN_UNSUPPORTED': 'unrecognized',
        'KNOWN_UNIMPLEMENTED': 'unimplemented',
        'ERROR_SYNTAX': 'syntaxerrors',
        'UNPROCESSED': 'unprocessed'

    }
    with open(os.path.join(config_conversion_path, html_file), 'w') as output_html:
        with open(os.path.join(config_conversion_path, secure_filename(filename)), 'r') as input_file:
            with open(os.path.join(config_conversion_path, output_csv), 'rb') as csvfile:
                output_html.write('<pre style="background-color:white;border:none;word-wrap:initial;">\n')
                reader = csv.reader(csvfile)
                last_category = ""
                for config_line in input_file:
                    next_row = reader.next()
                    if next_row and len(next_row) >= 2:

                        category = next_row[1].strip()
                        if category != last_category:
                            if last_category != "":
                                output_html.write('</div>')
                            html_class = map_csv_category_to_final_category.get(category)
                            output_html.write('<div class="' + html_class + '">\n')
                            last_category = category
                        output_html.write('<code>' + config_line.rstrip('\n') + '</code>\n')
                output_html.write('</div>\n')
                output_html.write('</pre>')
    return send_from_directory(config_conversion_path, html_file, cache_timeout=0)


@asr9k_64_migrate.route('/upload_config_to_server_repository')
def upload_config_to_server_repository():
    server_id = request.args.get('server_id', -1, type=int)
    server_directory = request.args.get('server_directory', '', type=str)
    filename = request.args.get('filename', '', type=str)

    if server_id == -1:
        logger.error('No server repository selected.')
        return jsonify(status='No server repository selected.')

    db_session = DBSession()
    server = get_server_by_id(db_session, server_id)

    if not server:
        logger.error('Selected server repository not found in database.')
        return jsonify(status='Selected server repository not found in database.')

    if not server_directory:
        server_directory = None

    if not filename:
        logger.error('No filename selected.')
        return jsonify(status='No filename selected.')

    config_conversion_path = get_config_conversion_path()

    stripped_filename = get_stripped_filename(filename)

    output_iox = stripped_filename + ".iox"

    output_cal = stripped_filename + ".cal"

    status = upload_files_to_server_repository(os.path.join(config_conversion_path, output_iox),
                                               server, server_directory, output_iox)
    if status == "OK":
        status = upload_files_to_server_repository(os.path.join(config_conversion_path, output_cal),
                                                   server, server_directory, output_cal)
    return jsonify(status=status)


def get_stripped_filename(filename):
    secure_file_name = secure_filename(filename)
    return secure_file_name.rsplit('.', 1)[0]


def upload_files_to_server_repository(sourcefile, server, selected_server_directory, destfile):
    """
    Upload files from their locations in the host linux system to the FTP/TFTP/SFTP server repository.

    Arguments:
    :param sourcefile: one string file path that points to a file on the system where CSM is hosted.
                        The paths are all relative to csm/csmserver/.
                        For example, if the source file is in csm_data/migration/filename,
                        sourcefile = "../../csm_data/migration/filename"
    :param server: the associated server repository object stored in CSM database
    :param selected_server_directory: the designated directory in the server repository
    :param destfile: one string filename that the source files should be named after being copied to
                          the designated directory in the server repository. i.e., "thenewfilename"
    :return: True if no error occurred.
    """
    server_type = server.server_type
    if server_type == ServerType.TFTP_SERVER:
        tftp_server = TFTPServer(server)
        try:
            tftp_server.upload_file(sourcefile, destfile,
                                    sub_directory=selected_server_directory)
        except Exception as inst:
            print(inst)
            logger.error('Unable to upload file to selected server directory in repository.')
            return 'Unable to upload file'

    elif server_type == ServerType.FTP_SERVER:
        ftp_server = FTPServer(server)
        try:
            ftp_server.upload_file(sourcefile, destfile,
                                   sub_directory=selected_server_directory)
        except Exception as inst:
            print(inst)
            logger.error('Unable to upload file to selected server directory in repository.')
            return 'Unable to upload file'

    elif server_type == ServerType.SFTP_SERVER:
        sftp_server = SFTPServer(server)
        try:
            sftp_server.upload_file(sourcefile, destfile,
                                    sub_directory=selected_server_directory)
        except Exception as inst:
            print(inst)
            logger.error('Unable to upload file to selected server directory in repository.')
            return 'Unable to upload file'

    else:
        logger.error('Only FTP, SFTP and TFTP server repositories are supported for this action.')
        return jsonify(status='Only FTP, SFTP and TFTP server repositories are supported for this action')

    return 'OK'


@asr9k_64_migrate.route('/migration', methods=['GET', 'POST'])
@login_required
def migration():
    # only operator and above can schedule migration
    if not can_install(current_user):
        render_template('user/not_authorized.html', user=current_user)

    # temp_user_dir = create_temp_user_directory(current_user.username)
    # config_file_path = os.path.normpath(os.path.join(temp_user_dir, "config_conversion"))
    # create_directory(config_file_path)
    # current_app.config['UPLOAD_FOLDER'] = config_file_path
    # print "current_app.config.get('UPLOAD_FOLDER') = " + current_app.config.get('UPLOAD_FOLDER')

    db_session = DBSession()

    return_url = get_return_url(request, 'install_dashboard')

    schedule_form = init_schedule_form(db_session, request, get=request.method == 'GET')
    config_form = init_config_form(db_session, request, get=request.method == 'GET')

    if request.method == 'POST':
        print(str(config_form.data))
        if config_form.hidden_submit_config_form.data == "True":
            return convert_config(db_session, request, 'asr9k_64_migrate/migration.html', schedule_form)

        # Retrieves from the multi-select box
        hostnames = schedule_form.hidden_hosts.data.split(',')

        install_action = schedule_form.install_action.data

        if hostnames is not None:
            print(str(schedule_form.data))
            print(str(hostnames))
            dependency_list = schedule_form.hidden_dependency.data.split(',')
            index = 0
            for hostname in hostnames:

                host = get_host(db_session, hostname)

                if host is not None:

                    db_session = DBSession()
                    scheduled_time = schedule_form.scheduled_time_UTC.data
                    software_packages = schedule_form.hidden_software_packages.data
                    server = schedule_form.hidden_server.data
                    server_directory = schedule_form.hidden_server_directory.data
                    custom_command_profile = ','.join([str(i) for i in schedule_form.custom_command_profile.data])

                    if InstallAction.MIGRATION_AUDIT in install_action:
                        host.context[0].data['hardware_audit_version'] = \
                            schedule_form.hidden_hardware_audit_version.data

                    if InstallAction.PRE_MIGRATE in install_action:
                        host.context[0].data['config_filename'] = schedule_form.hidden_config_filename.data
                        host.context[0].data['override_hw_req'] = schedule_form.hidden_override_hw_req.data

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
        return render_template('asr9k_64_migrate/migration.html',
                               schedule_form=schedule_form,
                               install_action=get_install_migrations_dict(),
                               server_time=datetime.datetime.utcnow(),
                               system_option=SystemOption.get(db_session),
                               config_form=config_form,
                               input_filename="",
                               err_msg="",
                               )


def init_schedule_form(db_session, http_request, get=False):
    hosts = get_host_list(db_session)
    if hosts is None:
        abort(404)

    schedule_form = ScheduleMigrationForm(http_request.form)
    fill_regions(schedule_form.region.choices)
    fill_hardware_audit_version(schedule_form.hardware_audit_version.choices)
    fill_custom_command_profiles(schedule_form.custom_command_profile.choices)

    if get:
        # Initialize the hidden fields

        schedule_form.hidden_server_name.data = ''
        schedule_form.hidden_server.data = -1
        schedule_form.hidden_server_directory.data = ''
        schedule_form.hidden_pending_downloads.data = ''
        schedule_form.hidden_region.data = -1
        schedule_form.hidden_hosts.data = ''
        schedule_form.hidden_software_packages.data = ''
        schedule_form.hidden_edit.data = 'False'
        schedule_form.hidden_config_filename.data = ''
        schedule_form.hidden_override_hw_req.data = '0'
        schedule_form.hidden_dependency.data = ''
        schedule_form.hidden_hardware_audit_version.data = ''
    return schedule_form


def init_config_form(db_session, http_request, get=False):
    config_form = ConfigConversionForm(http_request.form)
    servers = get_server_list(db_session)

    fill_servers(config_form.select_server.choices, servers, False)

    if get:
        config_form.hidden_submit_config_form.data = 'False'

    return config_form


@asr9k_64_migrate.route('/hosts/<hostname>/schedule_install/<int:id>/edit/', methods=['GET', 'POST'])
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

    return_url = get_return_url(request, 'host_dashboard')

    schedule_form = ScheduleMigrationForm(request.form)

    # Fills the selections
    fill_servers(schedule_form.server_dialog_server.choices, host.region.servers, include_local=False)
    fill_custom_command_profiles(schedule_form.custom_command_profile.choices)
    fill_hardware_audit_version(schedule_form.hardware_audit_version.choices)

    if request.method == 'POST':
        if install_job is not None:
            # In Edit mode, the install_action UI on HostScheduleForm is disabled (not allowed to change).
            # Thus, there will be no value returned by form.install_action.data.  So, re-use the existing ones.
            install_action = [ install_job.install_action ]
        else:
            install_action = schedule_form.install_action.data

        scheduled_time = schedule_form.scheduled_time_UTC.data
        software_packages = schedule_form.hidden_software_packages.data
        server = schedule_form.hidden_server.data
        server_directory = schedule_form.hidden_server_directory.data
        custom_command_profile = ','.join([str(i) for i in schedule_form.custom_command_profile.data])

        if InstallAction.MIGRATION_AUDIT in install_action:
            host.context[0].data['hardware_audit_version'] = \
                schedule_form.hidden_hardware_audit_version.data

        if InstallAction.PRE_MIGRATE in install_action:
            host.context[0].data['config_filename'] = schedule_form.hidden_config_filename.data
            host.context[0].data['override_hw_req'] = schedule_form.hidden_override_hw_req.data

        # install_action is a list object which can only contain one install action
        # at this editing time, accept the selected dependency if any

        dependency = int(schedule_form.hidden_dependency.data)
        create_or_update_install_job(db_session=db_session, host_id=host.id, install_action=install_action[0],
                                     scheduled_time=scheduled_time, software_packages=software_packages,
                                     server=server, server_directory=server_directory,
                                     custom_command_profile=custom_command_profile, dependency=dependency,
                                     install_job=install_job)

        return redirect(url_for(return_url, hostname=hostname))

    elif request.method == 'GET':
        # Initialize the hidden fields
        schedule_form.hidden_server.data = -1
        schedule_form.hidden_server_name.data = ''
        schedule_form.hidden_server_directory.data = ''
        schedule_form.hidden_pending_downloads.data = ''
        schedule_form.hidden_edit.data = install_job is not None

        schedule_form.hidden_region.data = str(host.region.name)
        fill_default_region(schedule_form.region.choices, host.region)
        schedule_form.hidden_hosts.data = hostname
        schedule_form.hidden_dependency.data = ''

        # In Edit mode
        if install_job is not None:
            schedule_form.install_action.data = install_job.install_action

            if install_job.custom_command_profile_id:
                ids = [int(id) for id in install_job.custom_command_profile_id.split(',')]
                schedule_form.custom_command_profile.data = ids

            schedule_form.hidden_override_hw_req.data = host.context[0].data.get('override_hw_req')
            schedule_form.hidden_config_filename.data = host.context[0].data.get('config_filename')
            schedule_form.hidden_hardware_audit_version.data = host.context[0].data.get('hardware_audit_version')

            if install_job.server_id is not None:
                schedule_form.hidden_server.data = install_job.server_id
                server = get_server_by_id(db_session, install_job.server_id)
                if server is not None:
                    schedule_form.hidden_server_name.data = server.hostname

                schedule_form.hidden_server_directory.data = '' if install_job.server_directory is None \
                    else install_job.server_directory

            schedule_form.hidden_pending_downloads.data = '' if install_job.pending_downloads is None \
                else install_job.pending_downloads

            # Form a line separated list for the textarea
            if install_job.packages is not None:

                schedule_form.hidden_software_packages.data = install_job.packages

            if install_job.dependency is not None:
                schedule_form.hidden_dependency.data = str(install_job.dependency)
            else:
                schedule_form.hidden_dependency.data = '-1'

            if install_job.scheduled_time is not None:
                schedule_form.scheduled_time_UTC.data = get_datetime_string(install_job.scheduled_time)

    return render_template('asr9k_64_migrate/migration.html', schedule_form=schedule_form, system_option=SystemOption.get(db_session),
                           host=host, server_time=datetime.datetime.utcnow(), install_job=install_job,
                           return_url=return_url, install_action=get_install_migrations_dict(), input_filename="",
                           err_msg="")


@asr9k_64_migrate.route('/select_host.html')
def select_host():
    return render_template('asr9k_64_migrate/select_host.html')


@asr9k_64_migrate.route('/api/get_dependencies/')
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
            # Firstly, check if dependency action is scheduled or in progress, if so, add dependency
            last_unfinished_dependency_job = get_last_unfinished_install_action(db_session, dependency,
                                                                                get_host(db_session, hostname).id)
            if last_unfinished_dependency_job:
                dependency_list.append(last_unfinished_dependency_job.id)
            else:
                # Secondly, check if dependency action most recently completed or failed
                last_completed_or_failed_dependency_job = get_last_completed_or_failed_install_action(db_session,
                                                                                                      dependency,
                                                                                                      host.id)
                if last_completed_or_failed_dependency_job:
                    if last_completed_or_failed_dependency_job.status == JobStatus.COMPLETED:
                        dependency_list.append('-1')
                    else:
                        dependency_list.append(last_completed_or_failed_dependency_job.install_job_id)
                else:
                    disqualified_count += 1
                    dependency_list.append('-2')
        else:
            dependency_list.append('-1')
    return jsonify(**{'data': [{'dependency_list': dependency_list, 'disqualified_count':  disqualified_count}]})


def download_latest_config_migration_tool():
    """Check if the latest NoX is in file. Download if not."""
    fileloc = get_migration_directory()

    (success, date) = get_nox_binary_publish_date()
    if not success:
        return False, "Failed to get the publish date of the most recent NoX conversion tool on CCO."

    need_new_nox = False

    if os.path.isfile(fileloc + NOX_PUBLISH_DATE):
        try:
            with open(fileloc + NOX_PUBLISH_DATE, 'r') as f:
                current_date = f.readline()

            if date != current_date:
                need_new_nox = True
            f.close()
        except:
            return False, 'Exception was thrown when reading file ' + fileloc + NOX_PUBLISH_DATE

    else:
        need_new_nox = True

    if need_new_nox:

        check_32_or_64_system = subprocess.Popen(['uname', '-a'], stdout=subprocess.PIPE)
        out, err = check_32_or_64_system.communicate()
        if err:
            return False, 'Error when trying to determine whether the ' + \
                          'linux system that you are hosting CSM on is ' + \
                          '32 bit or 64 bit with command "uname -a".'

        if "x86_64" in out:
            nox_to_use = NOX_64_BINARY
        else:
            return False, 'NoX is not available for 32 bit linux.'
            # nox_to_use = NOX_32_BINARY

        (success, error_msg) = get_file_http(nox_to_use, fileloc)
        if not success:
            return False, error_msg
        try:
            with open(fileloc + NOX_PUBLISH_DATE, 'w') as nox_publish_date_file:
                nox_publish_date_file.write(date)
            nox_publish_date_file.close()
        except:
            nox_publish_date_file.close()
            return False, 'Exception was thrown when writing file ' + fileloc + NOX_PUBLISH_DATE

    return True, 'None'


@asr9k_64_migrate.route('/api/get_latest_config_migration_tool/')
@login_required
def get_latest_config_migration_tool():
    """Check if the latest NoX is in file. Download if not."""
    success, err_msg = download_latest_config_migration_tool()

    return jsonify( **{'data': [ { 'error': err_msg } ] } )


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
        "migrationaudit":InstallAction.MIGRATION_AUDIT,
        "premigrate": InstallAction.PRE_MIGRATE,
        "migrate": InstallAction.MIGRATE_SYSTEM,
        "postmigrate": InstallAction.POST_MIGRATE,
        "allformigrate": InstallAction.ALL_FOR_MIGRATE
    }


def fill_hardware_audit_version(choices):
    # Remove all the existing entries
    del choices[:]
    choices.append(('', ''))

    with open('./asr9k_64bit/migration_supported_hw.json') as data_file:
        supported_hw = json.load(data_file)

    versions = supported_hw.keys()
    for version in reversed(versions):
        choices.append((version, version))


class ScheduleMigrationForm(Form):
    install_action = SelectMultipleField('Install Action', coerce=str, choices=[('', '')])

    scheduled_time = StringField('Scheduled Time', [required()])
    scheduled_time_UTC = HiddenField('Scheduled Time')
    custom_command_profile = SelectMultipleField('Custom Command Profile', coerce=int, choices=[(-1, '')])

    region = SelectField('Region', coerce=int, choices=[(-1, '')])
    role = SelectField('Role', coerce=str, choices=[('Any', 'Any')])
    software = SelectField('Software Version', coerce=str, choices=[('Any', 'Any')])

    server_dialog_target_software = StringField('Target Software Release')
    server_dialog_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])
    server_dialog_server_directory = SelectField('Server Directory', coerce=str, choices=[('', '')])

    hidden_region = HiddenField('')
    hidden_hosts = HiddenField('')

    hidden_server = HiddenField('')
    hidden_server_name = HiddenField('')
    hidden_server_directory = HiddenField('')
    hidden_pending_downloads = HiddenField('Pending Downloads')
    hidden_software_packages = HiddenField('')

    hidden_override_hw_req = HiddenField('')
    hidden_config_filename = HiddenField('')

    hidden_edit = HiddenField('Edit')

    hidden_dependency = HiddenField('')

    hardware_audit_version = SelectField('ASR9K-64 Software Version', coerce=str, choices=[('Any', 'Any')])
    hidden_hardware_audit_version = HiddenField('')


class ConfigConversionForm(Form):
    select_server = SelectField('Server Repository', coerce=int, choices=[(-1, '')])
    select_server_directory = SelectField('Server Directory', coerce=str, choices=[('', '')])
    # select_file = SelectField('Configuration File', coerce=str, choices=[('', '')])
    # hidden_server = HiddenField('')
    # hidden_server_name = HiddenField('')
    # hidden_server_directory = HiddenField('')
    # hidden_config_file = HiddenField('')
    hidden_submit_config_form = HiddenField('')
