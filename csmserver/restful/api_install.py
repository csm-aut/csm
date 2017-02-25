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
# ==============================================================================

from flask import jsonify

from api_utils import ENVELOPE
from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import APIStatus
from api_utils import validate_url_parameters
from api_utils import convert_value_to_list
from api_utils import validate_required_keys_in_dict
from api_utils import validate_acceptable_keys_in_dict
from api_utils import convert_json_request_to_list
from api_utils import failed_response

from api_constants import HTTP_OK
from api_constants import HTTP_BAD_REQUEST
from api_constants import HTTP_MULTI_STATUS_ERROR

from utils import is_empty

from sqlalchemy import and_

from database import DBSession

from models import InstallJob
from models import InstallJobHistory

from constants import JobStatus
from constants import InstallAction
from constants import get_log_directory

from common import delete_install_job_dependencies
from common import create_or_update_install_job
from common import get_server
from common import get_server_by_id
from common import get_host
from common import get_host_by_id
from common import download_session_logs
from common import get_custom_command_profile
from common import get_custom_command_profile_by_id

from datetime import datetime, timedelta
from operator import itemgetter

import re
import os

KEY_ID = 'id'
KEY_HOSTNAME = 'hostname'
KEY_STATUS = 'status'
KEY_INSTALL_ACTION = 'install_action'
KEY_SOFTWARE_PACKAGES = 'software_packages'
KEY_SCHEDULED_TIME = 'scheduled_time'
KEY_START_TIME = 'start_time'
KEY_STATUS_TIME = 'status_time'
KEY_UTC_OFFSET = 'utc_offset'
KEY_DEPENDENCY = 'dependency'
KEY_SERVER_REPOSITORY = 'server_repository'
KEY_SERVER_DIRECTORY = 'server_directory'
KEY_CUSTOM_COMMAND_PROFILE = 'command_profile'

KEY_UTC_SCHEDULED_TIME = 'utc_scheduled_time'
KEY_TRACE = 'trace'
KEY_CREATED_BY = 'created_by'
KEY_DELETED_DEPENDENCIES = 'deleted_dependencies'
KEY_INSTALL_JOB_LIST = 'install_job_list'

supported_install_actions = [InstallAction.PRE_UPGRADE, InstallAction.INSTALL_ADD, InstallAction.INSTALL_ACTIVATE,
                             InstallAction.POST_UPGRADE, InstallAction.INSTALL_COMMIT, InstallAction.INSTALL_REMOVE,
                             InstallAction.INSTALL_DEACTIVATE]

acceptable_keys = [KEY_HOSTNAME, KEY_INSTALL_ACTION, KEY_SCHEDULED_TIME, KEY_UTC_OFFSET, KEY_CUSTOM_COMMAND_PROFILE,
                   KEY_DEPENDENCY, KEY_SERVER_REPOSITORY, KEY_SERVER_DIRECTORY, KEY_SOFTWARE_PACKAGES]

required_keys_dict = {InstallAction.PRE_UPGRADE: [KEY_HOSTNAME],
                      InstallAction.INSTALL_ADD: [KEY_HOSTNAME, KEY_SERVER_REPOSITORY, KEY_SOFTWARE_PACKAGES],
                      InstallAction.INSTALL_ACTIVATE: [KEY_HOSTNAME, KEY_SOFTWARE_PACKAGES],
                      InstallAction.POST_UPGRADE: [KEY_HOSTNAME],
                      InstallAction.INSTALL_COMMIT: [KEY_HOSTNAME],
                      InstallAction.INSTALL_REMOVE: [KEY_HOSTNAME, KEY_SOFTWARE_PACKAGES],
                      InstallAction.INSTALL_DEACTIVATE: [KEY_HOSTNAME, KEY_SOFTWARE_PACKAGES]}


def api_create_install_request(request):
    """
    Install Action: Pre-Upgrade, Post-Upgrade, and Commit

        POST: http://localhost:5000/api/v1/install
        BODY:
            [ {'hostname': 'My Host',
               'install_action': 'Post-Upgrade',
               'scheduled_time': '05-02-2016 08:00 AM',
               'command_profile': 'Edge Devices',
               'dependency': 'Add'} ]

    Install Action: Add
        BODY:
            [ {'hostname': 'My Host',
               'install_action': 'Add',
               'scheduled_time': '05-02-2016 08:00 AM',
               'server_repository': 'My FTP Server',
               'software_packages': 'asr9k-px-5.3.3.CSCuz05961.pie,
                       asr9k-px-5.3.3.CSCux89921.pie,
                       asr9k-px-5.3.3.CSCuy03335.pie',
               'dependency': 'Pre-Upgrade'} ]

    Install Action: Activate, Remove, Deactivate
        BODY:
            [ {'hostname': 'My Host',
               'install_action': 'Activate',
               'scheduled_time': '05-02-2016 08:00 AM',
               'software_packages': 'asr9k-px-5.3.3.CSCuz05961.pie,
                       asr9k-px-5.3.3.CSCux89921.pie,
                       asr9k-px-5.3.3.CSCuy03335.pie',
               'dependency': '101'} ]


        RETURN:
            {"api_response": {
                "install_job_list": [ {"status": "SUCCESS", "hostname": "My Host", "install_request_id": 101},
                               {"status": "FAILED", "hostname": "My Host 2", "status_message": "Unable to locate host"} ]

                }
            }
    """

    rows = []
    error_found = False
    db_session = DBSession()
    # ----------------------------  first phase is to attempt the data validation ---------------------------- #

    entries = []
    json_list = convert_json_request_to_list(request)

    for data in json_list:
        row = dict()
        try:
            validate_required_keys_in_dict(data, [KEY_INSTALL_ACTION])

            install_action = data[KEY_INSTALL_ACTION]
            if install_action not in supported_install_actions:
                raise ValueError("'{}' is not a valid install action.".format(install_action))

            validate_acceptable_keys_in_dict(data, acceptable_keys)
            validate_required_keys_in_dict(data, required_keys_dict[install_action])

            hostname = data[KEY_HOSTNAME]
            host = get_host(db_session, hostname)
            if host is None:
                raise ValueError("'{}' is not a valid hostname.".format(data[KEY_HOSTNAME]))

            if KEY_SERVER_REPOSITORY in data.keys():
                server = get_server(db_session, data[KEY_SERVER_REPOSITORY])
                if server is None:
                    raise ValueError("'{}' is not a valid server repository.".format(data[KEY_SERVER_REPOSITORY]))

            if KEY_CUSTOM_COMMAND_PROFILE in data.keys():
                custom_command_profile_names = convert_value_to_list(data, KEY_CUSTOM_COMMAND_PROFILE)
                for custom_command_profile_name in custom_command_profile_names:
                    command_profile = get_custom_command_profile(db_session, custom_command_profile_name)
                    if command_profile is None:
                        raise ValueError("'{}' is not a valid custom command profile.".format(custom_command_profile_name))

            if KEY_SOFTWARE_PACKAGES in data.keys() and is_empty(data[KEY_SOFTWARE_PACKAGES]):
                raise ValueError("Software packages if specified cannot be empty.")

            # Check time fields and validate their values
            if KEY_SCHEDULED_TIME not in data.keys():
                row[KEY_UTC_SCHEDULED_TIME] = datetime.utcnow()
            elif KEY_UTC_OFFSET not in data.keys():
                raise ValueError("Missing utc_offset. If scheduled_time is submitted, utc_offset is also required.")
            elif not verify_utc_offset(data[KEY_UTC_OFFSET]):
                raise ValueError("Invalid utc_offset: Must be in '<+|->dd:dd' format and be between -12:00 and +14:00.")
            else:
                try:
                    time = datetime.strptime(data[KEY_SCHEDULED_TIME], "%m-%d-%Y %I:%M %p")
                    row[KEY_UTC_SCHEDULED_TIME] = get_utc_time(time, data[KEY_UTC_OFFSET])
                except ValueError:
                    raise ValueError("Invalid scheduled_time: {} must be in 'mm-dd-yyyy hh:mm AM|PM' format.".
                                     format(data[KEY_SCHEDULED_TIME]))

            # Handle duplicate entry.  It is defined by the hostname and install_action pair.
            if (hostname, install_action) not in entries:
                entries.append((hostname, install_action))
            else:
                raise ValueError("More than one entry with the same hostname: '{}' and install_action: '{}'. "
                                 "Remove any duplicate and resubmit.".format(hostname, install_action))

        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            error_found = True

        # Add the original key value pairs to the new array.
        for key in data.keys():
            row[key] = data[key]

        rows.append(row)

    # End of loop

    if error_found:
        for row in rows:
            if STATUS not in row.keys():
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = 'Not submitted. Check other jobs for error message.'

            if KEY_UTC_SCHEDULED_TIME in row.keys():
                row.pop(KEY_UTC_SCHEDULED_TIME)

        return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), HTTP_BAD_REQUEST

    print('ROW', rows)

    # sorted_list = sorted(rows, key=lambda k: (k[KEY_HOSTNAME], k[KEY_INSTALL_ACTION]))
    json_data = sorted(rows, cmp=getKey)
    sorted_list = sorted(json_data, key=itemgetter('utc_scheduled_time', 'hostname'))

    print('SORTED_LIST', sorted_list)

    # ----------------------------  Second phase is to attempt the job creation ---------------------------- #
    rows = []
    error_found = False
    for data in sorted_list:
        row = dict()
        try:
            pass

            install_action = data[KEY_INSTALL_ACTION]

            server_id = -1
            if KEY_SERVER_REPOSITORY in data.keys():
                server = get_server(db_session, data[KEY_SERVER_REPOSITORY])
                if server is not None:
                    server_id = server.id

            if KEY_SERVER_DIRECTORY in data.keys():
                server_directory = data[KEY_SERVER_DIRECTORY]
            else:
                server_directory = ''

            install_job = create_or_update_install_job(db_session,
                                                       host_id=get_host(db_session, install_request['hostname']).id,
                                                       install_action=install_action,
                                                       scheduled_time=utc_scheduled_time,
                                                       software_packages=software_packages,
                                                       server=server_id,
                                                       server_directory=server_directory,
                                                       custom_command_profile=command_profile,
                                                       dependency=install_request['dependency'])

        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


    """
    db_session = DBSession()
    rows = []

    # Install job information is expected to be an array of dictionaries
    json_data = request.json

    install_actions = ['Pre-Upgrade', 'Add', 'Activate', 'Post-Upgrade', 'Commit', 'Remove', 'Deactivate']

    # Convert all scheduled_times to datetime.datetime objects.
    # If any job is invalid, no jobs will be run and all will be returned with status "Not run." except the invalid
    # job. The invalid job will have a status message relevant to the error seen.

    valid_request = True
    if type(json_data) is not list:
        json_data = [json_data]

    for r in json_data:
        row = {}
        try:
            if 'scheduled_time' not in r.keys():
                row['utc_scheduled_time'] = datetime.utcnow()
            elif 'utc_offset' not in r.keys():
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = 'Missing utc_offset. If scheduled_time is submitted, utc_offset is also required.'
                valid_request = False
            elif not verify_utc_offset(r['utc_offset']):
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = "Invalid utc_offset: Must be in '<+|->dd:dd' format and be between -12:00 and +14:00."
                valid_request = False
            else:
                try:
                    time = datetime.strptime(r['scheduled_time'], "%m-%d-%Y %I:%M %p")
                    r['utc_scheduled_time'] = get_utc_time(time, r['utc_offset'])
                except ValueError:
                    row[STATUS] = APIStatus.FAILED
                    row[STATUS_MESSAGE] = "Invalid scheduled_time: %s must be in 'mm-dd-yyyy hh:mm AM|PM' format." % r[
                        'scheduled_time']
                    valid_request = False

        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            rows = [row]
            db_session.rollback()
            return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), 400

        if STATUS not in row.keys():
            if 'hostname' not in r.keys():
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = 'Missing hostname.'
                valid_request = False
            elif not get_host(db_session, r['hostname']):
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = 'Invalid hostname: %s.' % r['hostname']
                valid_request = False
            elif 'install_action' not in r.keys() or \
                            r['install_action'] not in install_actions:
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = 'Missing or invalid install_action.'
                valid_request = False
            else:
                valid, msg = validate_install_request(db_session, r)
                if not valid:
                    row[STATUS] = APIStatus.FAILED
                    row[STATUS_MESSAGE] = msg
                    valid_request = False

        for key in r.keys():
            row[key] = r[key]


        rows.append(row)

    print('ROWS', rows)

    if not valid_request:
        for r in rows:
            if STATUS not in r.keys():
                r[STATUS] = APIStatus.FAILED
                r[STATUS_MESSAGE] = 'Not submitted. Check other jobs for error message.'
            if 'utc_scheduled_time' in r.keys():
                r.pop('utc_scheduled_time')
        return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), 400
    """


    # Sort on install_action, then hostname, then scheduled_time
    json_data = sorted(rows, cmp=getKey)
    json_data = sorted(json_data, key=itemgetter('utc_scheduled_time', 'hostname'))

    """
    # Remove duplicates (defined as having the same hostname and install_action)
    install_requests = []
    entries =[]
    duplicate_flag = False
    for r in json_data:
        if (r['hostname'], r['install_action']) not in entries:
            install_requests.append(r)
            entries.append((r['hostname'], r['install_action']))
        else:
            duplicate_flag = True
            r[STATUS] = APIStatus.FAILED
            r[STATUS_MESSAGE] = "Duplicate entry detected. Duplicates are defined as entries with the same hostname and" \
                                " same install_action. Please remove one duplicate and resubmit."

    if duplicate_flag:
        rows = []
        for r in json_data:
            row = {}
            if STATUS not in r.keys():
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = "Not submitted. Check other jobs for error message."
            for key in r.keys():
                row[key] = r[key]
            rows.append(row)
        return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), 400
    """

    # For implicit dependencies
    dependency_list = {}
    order = ['Pre-Upgrade', 'Add', 'Activate', 'Post-Upgrade', 'Commit', 'Remove', 'Deactivate']

    rows = []
    error_found = False
    return_code = 200
    for install_request in install_requests:
        row = {}
        msg = ''
        # If dependency was not specified, there may be an implicit dependency
        if install_request['install_action'] in ['Deactivate', 'Remove']:
            install_request['dependency'] = 0
        if 'dependency' not in install_request.keys():
            install_request['dependency'] = 0
            if install_request['hostname'] in dependency_list.keys():
                last_id, last_action = dependency_list[install_request['hostname']][-1]
                if order.index(last_action) < order.index(install_request['install_action']):
                    install_request['dependency'] = last_id
        elif not str(install_request['dependency']).isdigit():
            # check for implicit dependencies before checking DB
            if install_request['hostname'] in dependency_list.keys():
                for id, action in dependency_list[install_request['hostname']]:
                    if action == install_request['dependency']:
                        install_request['dependency'] = id
                if not str(install_request['dependency']).isdigit():
                    host = get_host(db_session, install_request['hostname'])
                    install_request['dependency'], msg = get_dependency(db_session, install_request, host.id)
            else:
                host = get_host(db_session, install_request['hostname'])
                install_request['dependency'], msg = get_dependency(db_session, install_request, host.id)
        else:
            host = get_host(db_session, install_request['hostname'])
            install_request['dependency'], msg = get_dependency(db_session, install_request, host.id)

        if msg not in [APIStatus.SUCCESS, '']:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = msg
            row['install_action'] = install_request['install_action']
            row['hostname'] = install_request['hostname']
        else:
            utc_scheduled_time = install_request['utc_scheduled_time'].strftime("%m/%d/%Y %I:%M %p")
            if 'command_profile' in install_request.keys():
                command_profile = get_custom_command_profile(db_session, install_request['command_profile']).id
            else:
                command_profile = -1
            if 'server_repository' in install_request.keys():
                server = get_server(db_session, install_request['server_repository']).id
            else:
                server = -1
            if 'software_packages' in install_request.keys():
                software_packages = install_request['software_packages']
            else:
                software_packages = ""
            if 'server_directory' in install_request.keys():
                server_directory = install_request['server_directory']
            else:
                server_directory = ""
            try:
                install_job = create_or_update_install_job(db_session,
                                                           host_id=get_host(db_session, install_request['hostname']).id,
                                                           install_action=install_request['install_action'],
                                                           scheduled_time=utc_scheduled_time,
                                                           software_packages=software_packages,
                                                           server=server,
                                                           server_directory=server_directory,
                                                           custom_command_profile=command_profile,
                                                           dependency=install_request['dependency'])

                if install_request['install_action'] not in ['Remove', 'Deactivate']:
                    if install_request['hostname'] not in dependency_list:
                        dependency_list[install_request['hostname']] = []
                    dependency_list[install_request['hostname']].append((install_job.id, install_job.install_action))

                row[STATUS] = APIStatus.SUCCESS
                row['id'] = install_job.id
                row['install_action'] = install_job.install_action
                row['hostname'] = install_request['hostname']
            except Exception as e:
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = e.message
                row['install_action'] = install_request['install_action']
                row['hostname'] = install_request['hostname']
                db_session.rollback()
                error_found = True

        rows.append(row)

    if error_found:
        return_code = 207

    return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), return_code


def api_get_install_request(request):
    """
    GET:
    http://localhost:5000/api/v1/install
    http://localhost:5000/api/v1/install?id=1
    http://localhost:5000/api/v1/install?hostname=R1
    http://localhost:5000/api/v1/install?hostname=r1&install_action=Add
    http://localhost:5000/api/v1/install?hostname=R1&status="failed"
    """
    validate_url_parameters(request, [KEY_ID, KEY_HOSTNAME, KEY_INSTALL_ACTION, KEY_STATUS,
                                      KEY_SCHEDULED_TIME, KEY_UTC_OFFSET])
    clauses = []
    db_session = DBSession

    id = request.args.get(KEY_ID)
    hostname = request.args.get(KEY_HOSTNAME)
    install_action = request.args.get(KEY_INSTALL_ACTION)
    status = request.args.get(KEY_STATUS)
    scheduled_time = request.args.get(KEY_SCHEDULED_TIME)
    utc_offset = request.args.get(KEY_UTC_OFFSET)

    if utc_offset and '-' not in utc_offset and '+' not in utc_offset:
        utc_offset = "+" + utc_offset.strip()

    table_to_query = 'install_job'

    if id:
        # Use all() instead of first() so the return is a list type.
        install_jobs = db_session.query(InstallJob).filter(InstallJob.id == id).all()
        if not install_jobs:
            # It is possible that this query may result in multiple rows
            # 1) the install job id may be re-used by other hosts.
            # 2) if the install job was re-submitted.
            install_jobs = db_session.query(InstallJobHistory).filter(InstallJobHistory.install_job_id == id).all()
            table_to_query = 'install_job_history'
            if not install_jobs:
                raise ValueError("Install id '{}' does not exist in the database.".format(id))
    else:
        if hostname:
            host = get_host(db_session, hostname)
            if host:
                clauses.append(InstallJob.host_id == host.id)
            else:
                raise ValueError("Host '{}' does not exist in the database.".format(hostname))

        if install_action:
            if install_action not in [InstallAction.PRE_UPGRADE, InstallAction.INSTALL_ADD,
                                      InstallAction.INSTALL_ACTIVATE, InstallAction.POST_UPGRADE,
                                      InstallAction.INSTALL_COMMIT, InstallAction.INSTALL_REMOVE,
                                      InstallAction.INSTALL_DEACTIVATE]:
                raise ValueError("'{}' is an invalid install action.".format(install_action))

            clauses.append(InstallJob.install_action == install_action)

        if status:
            if status not in [JobStatus.SCHEDULED, JobStatus.IN_PROGRESS, JobStatus.FAILED, JobStatus.COMPLETED]:
                raise ValueError("'{}' is an invalid job status.".format(status))

            clauses.append(InstallJob.status == (None if status == JobStatus.SCHEDULED else status))

        if status == JobStatus.COMPLETED:
            table_to_query = 'install_job_history'

        if scheduled_time:
            if not utc_offset:
                raise ValueError("utc_offset must be specified if scheduled_time is specified.")
            elif not verify_utc_offset(utc_offset):
                raise ValueError("Invalid utc_offset: Must be in '<+|->dd:dd' format and be between -12:00 and +14:00.")
            try:
                time = datetime.strptime(scheduled_time, "%m-%d-%Y %I:%M %p")
                time_utc = get_utc_time(time, utc_offset)
                clauses.append(InstallJob.scheduled_time >= time_utc)
            except:
                raise ValueError("Invalid scheduled_time: '{}' must be in 'mm-dd-yyyy hh:mm AM|PM' format.".format(time))

        install_jobs = get_install_jobs(table_to_query, db_session, clauses)

    rows = []
    error_found = False

    for install_job in install_jobs:
        row = []
        try:
            row = get_install_job_info(db_session, install_job, utc_offset)
        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def get_install_job_info(db_session, install_job, utc_offset):
    row = dict()

    if install_job.__class__.__name__ == 'InstallJob':
        row[KEY_ID] = install_job.id

        server = get_server_by_id(db_session, install_job.server_id)
        row[KEY_SERVER_REPOSITORY] = server.hostname if server else ""
        row[KEY_SERVER_DIRECTORY] = install_job.server_directory if install_job.server_directory else ""

        custom_command_profile_names = []
        if install_job.custom_command_profile_ids:
            for custom_command_profile_id in install_job.custom_command_profile_ids.split(','):
                custom_command_profile = get_custom_command_profile_by_id(db_session, custom_command_profile_id)
                if custom_command_profile is not None:
                    custom_command_profile_names.append(custom_command_profile.profile_name)

        row[KEY_CUSTOM_COMMAND_PROFILE] = custom_command_profile_names

    else:
        row[KEY_ID] = install_job.install_job_id

    row[KEY_INSTALL_ACTION] = install_job.install_action
    row[KEY_DEPENDENCY] = install_job.dependency if install_job.dependency else ""

    if utc_offset and verify_utc_offset(utc_offset):
        if install_job.scheduled_time:
            row[KEY_SCHEDULED_TIME] = get_local_time(install_job.scheduled_time, utc_offset).strftime(
                "%m-%d-%Y %I:%M %p")
        else:
            row[KEY_SCHEDULED_TIME] = ""

        if install_job.start_time:
            row[KEY_START_TIME] = get_local_time(install_job.start_time, utc_offset).strftime(
                "%m-%d-%Y %I:%M %p")
        else:
            row[KEY_START_TIME] = ""

        if install_job.status_time:
            row[KEY_STATUS_TIME] = get_local_time(install_job.status_time, utc_offset).strftime(
                "%m-%d-%Y %I:%M %p")
        else:
            row[KEY_STATUS_TIME] = ""

    else:
        row[KEY_SCHEDULED_TIME] = install_job.scheduled_time if install_job.scheduled_time else ""
        row[KEY_START_TIME] = install_job.start_time if install_job.start_time else ""
        row[KEY_STATUS_TIME] = install_job.status_time if install_job.status_time else ""

    row[KEY_SOFTWARE_PACKAGES] = install_job.packages if install_job.packages else ""
    row[KEY_STATUS] = install_job.status if install_job.status else JobStatus.SCHEDULED
    row[KEY_TRACE] = install_job.trace if install_job.trace else ""
    row[KEY_CREATED_BY] = install_job.created_by if install_job.created_by else ""
    row[KEY_HOSTNAME] = get_host_by_id(db_session, install_job.host_id).hostname if install_job.host_id else ""

    return row



    """
    install_job_clauses = []
    install_job_history_clauses = [InstallJobHistory.status == 'completed']


    utc_offset = request.args.get('utc_offset')
    if utc_offset and '-' not in utc_offset and '+' not in utc_offset:
        utc_offset = "+" + utc_offset.strip()

    id = request.args.get('id')
    if id:
        install_jobs = db_session.query(InstallJob).filter((InstallJob.id==id)).all()
        if not install_jobs:
            install_history_jobs = db_session.query(InstallJobHistory).filter(InstallJobHistory.install_job_id==id).all()
        else:
            install_history_jobs = []
    else:
        hostname = request.args.get('hostname')
        if hostname:
            host = get_host(db_session, hostname)
            if host:
                host_id = host.id
            else:
                #return jsonify(**{ENVELOPE: 'Invalid hostname: %s.' % hostname}), 400
                return failed_response('Invalid hostname: %s.' % hostname)

            install_job_clauses.append(InstallJob.host_id == host_id)
            install_job_history_clauses.append(InstallJobHistory.host_id == host_id)

        install_action = request.args.get('install_action')
        if install_action:
            if install_action in ['Pre-Upgrade', 'Add', 'Activate', 'Post-Upgrade', 'Commit', 'Remove', 'Deactivate']:
                install_job_clauses.append(InstallJob.install_action == install_action)
                install_job_history_clauses.append(InstallJobHistory.install_action == install_action)
            else:
                #return jsonify(**{ENVELOPE: 'Invalid install_action: %s.' % install_action}), 400
                return failed_response('Invalid install_action: %s.' % install_action)

        status = request.args.get('status')
        if status:
            if status == 'scheduled':
                install_job_clauses.append(InstallJob.status.is_(None))
                install_job_history_clauses.append(False)
            elif status == 'in-progress': # get all the jobs, then code filter for status (Test first)
                install_job_clauses.append(InstallJob.status != None)
                install_job_clauses.append(InstallJob.status != 'failed')
                install_job_clauses.append(InstallJob.status != 'completed')
                install_job_history_clauses.append(False)
            elif status == 'failed':
                install_job_clauses.append(InstallJob.status == status)
                install_job_history_clauses.append(False)
            elif status == 'completed':
                install_job_clauses.append(InstallJob.status == status)
            else:
                #return jsonify(**{ENVELOPE: 'Invalid status: %s.' % status}), 400
                return failed_response('Invalid status: %s.' % status)

        scheduled_time = request.args.get('scheduled_time')
        if scheduled_time:
            if not utc_offset:
                return jsonify(**{ENVELOPE: 'utc_offset must be specified if scheduled_time is specified.'})
            elif not verify_utc_offset(utc_offset):
                return jsonify(**{
                    ENVELOPE: "Invalid utc_offset: Must be in '<+|->dd:dd' format and be between -12:00 and +14:00."})
            try:
                time = datetime.strptime(scheduled_time, "%m-%d-%Y %I:%M %p")
                time_utc = get_utc_time(time, utc_offset)
                install_job_clauses.append(InstallJob.scheduled_time >= time_utc)
                install_job_history_clauses.append(InstallJobHistory.scheduled_time >= time_utc)
            except:
                return jsonify(**{
                    ENVELOPE: "Invalid scheduled_time: %s must be in 'mm-dd-yyyy hh:mm AM|PM' format." % time})

        install_jobs = get_install_jobs_by_page(db_session, install_job_clauses)
        install_history_jobs = get_install_history_jobs_by_page(db_session, install_job_history_clauses)

    if is_empty(install_jobs) and is_empty(install_history_jobs):
        #return jsonify(**{ENVELOPE: {STATUS: APIStatus.FAILED, STATUS_MESSAGE: "No install job fits the given criteria"}}), 400
        return failed_response("No install job fits the given criteria")

    # If the get_..._by_page methods return an error string (more than 5000 results for one or both)
    if type(install_jobs) is str:
        #return jsonify(**{ENVELOPE: install_jobs}), 400
        return failed_response(install_jobs)
    elif type(install_history_jobs) is str:
        #return jsonify(**{ENVELOPE: install_history_jobs}), 400
        return failed_response(install_history_jobs)

    for install_job in install_jobs:
        row = {}
        row['id'] = install_job.id if install_job.id else ""
        row['install_action'] = install_job.install_action if install_job.install_action else ""
        row['dependency'] = install_job.dependency if install_job.dependency else ""

        if install_job.server_id:
            server = get_server_by_id(db_session, install_job.server_id)
            row['server_repository'] = server.hostname
        else:
            row['server_repository'] = ""

        if utc_offset and verify_utc_offset(utc_offset):
            if install_job.scheduled_time:
                row['scheduled_time'] = get_local_time(install_job.scheduled_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")
            else:
                row['scheduled_time'] = ""
            if install_job.start_time:
                row['start_time'] = get_local_time(install_job.start_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")
            else:
                row['start_time'] = ""
            if install_job.status_time:
                row['status_time'] = get_local_time(install_job.status_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")
            else:
                row['status_time'] = ""

        else:
            row['scheduled_time'] = install_job.scheduled_time if install_job.scheduled_time else ""
            row['start_time'] = install_job.start_time if install_job.start_time else ""
            row['status_time'] = install_job.status_time if install_job.status_time else ""

        row['server_directory'] = install_job.server_directory if install_job.server_directory else ""
        row['packages'] = install_job.packages if install_job.packages else ""

        #row['status'] = install_job.status if install_job.status else "scheduled"
        if install_job.status:
            if install_job.status not in ['failed', 'completed']:
                row['status'] = "in-progress - %s" % install_job.status
            else:
                row['status'] = install_job.status
        else:
            row['status'] = "scheduled"

        row['trace'] = install_job.trace if install_job.trace else ""
        row['created_by'] = install_job.created_by if install_job.created_by else ""
        row['hostname'] = get_host_by_id(db_session, install_job.host_id).hostname

        if not is_empty(install_job.custom_command_profile_id) and int(install_job.custom_command_profile_id) > 0:
            row['custom_command_profile'] = get_custom_command_profile_by_id(db_session,
                                                                             install_job.custom_command_profile_id).profile_name
        else:
            row['custom_command_profile'] = ""

        rows.append(row)

    for install_history_job in install_history_jobs:
        row = {}
        row['id'] = install_history_job.install_job_id if install_history_job.install_job_id else ""
        row['install_action'] = install_history_job.install_action if install_history_job.install_action else ""
        row['dependency'] = install_history_job.dependency if install_history_job.dependency else ""

        if utc_offset and verify_utc_offset(utc_offset):
            if install_history_job.scheduled_time:
                row['scheduled_time'] = get_local_time(install_history_job.scheduled_time, utc_offset).strftime(
                    "%m-%d-%Y %I:%M %p")
            else:
                row['scheduled_time'] = ""
            if install_history_job.start_time:
                row['start_time'] = get_local_time(install_history_job.start_time, utc_offset).strftime(
                    "%m-%d-%Y %I:%M %p")
            else:
                row['start_time'] = ""
            if install_history_job.status_time:
                row['status_time'] = get_local_time(install_history_job.status_time, utc_offset).strftime(
                    "%m-%d-%Y %I:%M %p")
            else:
                row['status_time'] = ""

        else:
            row['scheduled_time'] = install_history_job.scheduled_time if install_history_job.scheduled_time else ""
            row['start_time'] = install_history_job.start_time if install_history_job.start_time else ""
            row['status_time'] = install_history_job.status_time if install_history_job.status_time else ""

        row['packages'] = install_history_job.packages if install_history_job.packages else ""
        row['status'] = install_history_job.status if install_history_job.status else "scheduled"
        row['trace'] = install_history_job.trace if install_history_job.trace else ""
        row['created_by'] = install_history_job.created_by if install_history_job.created_by else ""
        row['hostname'] = get_host_by_id(db_session, install_history_job.host_id).hostname if install_history_job.host_id else ""

        rows.append(row)
        """

    return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}})


def api_delete_install_job(request):

    validate_url_parameters(request, [KEY_ID, KEY_HOSTNAME, KEY_STATUS])

    clauses = []
    db_session = DBSession

    id = request.args.get(KEY_ID)
    hostname = request.args.get(KEY_HOSTNAME)
    status = request.args.get(KEY_STATUS)

    if id:
        install_jobs = db_session.query(InstallJob).filter(InstallJob.id == id).all()
        if len(install_jobs) == 0:
            raise ValueError("Install id '{}' does not exist in the database.".format(id))
    else:
        if hostname:
            host = get_host(db_session, hostname)
            if host:
                clauses.append(InstallJob.host_id == host.id)
            else:
                raise ValueError("Host '{}' does not exist in the database.".format(hostname))

        if status:
            if status not in [JobStatus.SCHEDULED, JobStatus.FAILED]:
                raise ValueError("Invalid value for status: must be 'failed' or 'scheduled'.")

            clauses.append(InstallJob.status == (None if status == JobStatus.SCHEDULED else status))

        install_jobs = get_install_jobs('install_job', db_session, clauses)

    rows = []
    error_found = False

    for install_job in install_jobs:
        try:
            row = dict()
            row[KEY_ID] = install_job.id
            row[KEY_INSTALL_ACTION] = install_job.install_action

            host = get_host_by_id(db_session, install_job.host_id)
            if host is not None:
                row[KEY_HOSTNAME] = host.hostname

            # Only scheduled and failed jobs are deletable.
            if install_job.status is None or install_job.status == JobStatus.FAILED:
                db_session.delete(install_job)

                # If hostname is not specified, go ahead and delete all the install job's dependencies.
                # Otherwise, the dependencies should have already been selected for deletion.
                deleted_jobs = delete_install_job_dependencies(db_session, id) if hostname is None else []
                db_session.commit()

                if len(deleted_jobs) > 0:
                    row[KEY_DELETED_DEPENDENCIES] = deleted_jobs

                row[STATUS] = APIStatus.SUCCESS
            else:
                raise ValueError("Unable to delete install job '{}' as it is in progress.".format(install_job.id))

        except Exception as e:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def api_get_session_log(id):
    db_session = DBSession

    if not id:
        #return jsonify(**{ENVELOPE: "ID must be specified."}), 400
        return failed_response("ID must be specified.")

    install_job = db_session.query(InstallJob).filter((InstallJob.id == id)).first()
    if install_job is None:
        install_job = db_session.query(InstallJobHistory).filter((InstallJobHistory.install_job_id == id)).first()
    if install_job is None:
        #return jsonify(**{ENVELOPE: "Invalid ID."}), 400
        return failed_response("Invalid ID: %d." % id)

    if install_job.session_log is not None:
        log_dir = os.path.join(get_log_directory(), install_job.session_log)
        file_list = [os.path.join(log_dir, f) for f in os.listdir(log_dir)]
        return download_session_logs(file_list)
    else:
        return jsonify(**{ENVELOPE: "No log files."})


def get_install_jobs(install_job_table, db_session, clauses):

    if not is_empty(clauses):
        if db_session.query(install_job_table.id).filter(and_(*clauses)).count() > 5000:
            raise ValueError("Too many results; please refine your request.")
        else:
            return db_session.query(install_job_table).filter(and_(*clauses)).\
                order_by(install_job_table.id.asc()).all()
    else:
        if db_session.query(install_job_table.id).count() > 5000:
            raise ValueError("Too many results; please refine your request.")
        else:
            return db_session.query(install_job_table).order_by(install_job_table.id.asc()).all()

"""
def get_install_jobs_by_page(db_session, clauses):
    if not is_empty(clauses):
        if db_session.query(InstallJob.id).filter(and_(*clauses)).count() > 5000:
            return "Too many results; please refine your request."
        else:
            return db_session.query(InstallJob).filter(and_(*clauses)).\
                order_by(InstallJob.id.asc()).all()
    else:
        if db_session.query(InstallJob.id).count() > 5000:
            return "Too many results; please refine your request."
        else:
            return db_session.query(InstallJob).order_by(InstallJob.id.asc()).all()

def get_install_history_jobs_by_page(db_session, clauses):
        if not is_empty(clauses):
            if db_session.query(InstallJobHistory.id).filter(and_(*clauses)).count() > 5000:
                return "Too many results; please refine your request."
            else:
                return db_session.query(InstallJobHistory).filter(and_(*clauses)). \
                    order_by(InstallJobHistory.id.asc()).all()
        else:
            if db_session.query(InstallJobHistory.id).filter(InstallJobHistory.status =='completed').count() > 5000:
                return "Too many results; please refine your request."
            else:
                return db_session.query(InstallJobHistory).order_by(InstallJobHistory.install_job_id.asc()).all()
"""

# returns (int dependency, str msg)
def get_dependency(db_session, install_request, host_id):
    # Install jobs are already ordered from earliest to latest scheduled_time, then by hostname, then install_action
    # If dependency is not specified, it will be set to the last-processed install job for the same host, if one exists.
    if install_request['install_action'] in ['Remove', 'Deactivate']:
        return 0, APIStatus.SUCCESS
    else:
        dependency = str(install_request['dependency'])
        valid_actions = ['Pre-Upgrade', 'Add', 'Activate', 'Post-Upgrade', 'Commit', 'Remove', 'Deactivate']
        if dependency.isdigit():
            if int(dependency) > 0:
                install_job = db_session.query(InstallJob).filter(InstallJob.id == int(dependency)).first()
                if install_job:
                    if install_job.host_id != host_id:
                        return 0, 'Prerequisite job hostname does not match %s.' % install_request['hostname']
                    elif install_job.scheduled_time > install_request['utc_scheduled_time']:
                        return 0, 'Prerequisite job scheduled time is later than %s.' % install_request['utc_scheduled_time']
                    else:
                        return int(dependency), APIStatus.SUCCESS
                else:
                    return int(dependency), "Invalid dependency id; install job with id '%d' does not exist." % int(dependency)
            elif int(dependency) < 0:
                return 0, 'Invalid dependency value.'
            elif int(dependency) == 0:
                return 0, APIStatus.SUCCESS
        elif dependency not in valid_actions:
            return 0, 'Invalid dependency value.'
        else:
            install_jobs = db_session.query(InstallJob).filter(and_(InstallJob.host_id == host_id,
                                                                    InstallJob.install_action == dependency))\
                                                                    .order_by(InstallJob.scheduled_time.desc())
            for install_job in install_jobs:
                if install_job.scheduled_time <= install_request['utc_scheduled_time']:
                    return install_job.id, APIStatus.SUCCESS

            # No install_jobs currently scheduled for that host have both the specified action and scheduled_time
            # earlier than the current scheduled_time, or an action "less than" the current action and were submitted
            # in the same request
            return 0, APIStatus.SUCCESS


# returns (bool valid, str msg)
"""
def validate_install_request(db_session, install_request):
    requirements = {'Pre-Upgrade': ['hostname'],
                    'Add': ['hostname', 'server_repository', 'software_packages'],
                    'Activate': ['hostname', 'software_packages'],
                    'Post-Upgrade': ['hostname'],
                    'Commit': ['hostname'],
                    'Remove': ['hostname', 'software_packages'],
                    'Deactivate': ['hostname', 'software_packages']}

    for required in requirements[install_request['install_action']]:
        if required not in install_request.keys():
            return False, "Missing requirement: %s." % required

    if 'server_repository' in requirements[install_request['install_action']] and \
        not get_server(db_session, install_request['server_repository']):
        return False, "Invalid value for server_repository."

    if 'command_profile' in install_request.keys():
        if not get_custom_command_profile(db_session, install_request['command_profile']):
            return False, "Invalid value for command_profile; profile must exist."

    if 'software_packages' in requirements[install_request['install_action']] and \
        is_empty(install_request['software_packages']):
        return False, "software_packages cannot be empty"

    return True, "valid"
"""


def getKey(dict1, dict2):
    order = ['Pre-Upgrade', 'Add', 'Activate', 'Post-Upgrade', 'Commit', 'Remove', 'Deactivate']
    return order.index(dict1['install_action']) - order.index(dict2['install_action'])


def verify_utc_offset(utc_offset):
    """
    check to see that the utc_offset input is in the form '<+|->dd:dd'
    """
    r = re.compile('[+-]{1}\d{2}:\d{2}')
    if not r.match(utc_offset):
        return False
    else:
        hour = int(utc_offset[0:3])
        minute = int(utc_offset[4:])
        if -12 > hour or hour > 14 or minute > 59:
            return False
    return True


def get_utc_time(time, utc_offset):
    """
    utc_offset should be in the form '<+|->dd:dd'

    use verify_utc_offset to confirm before using this function
    """
    hours = int(utc_offset[0:3])
    minutes = int(utc_offset[4:])

    utc_time = time - timedelta(hours=hours, minutes=minutes)
    return utc_time


def get_local_time(utc_time, utc_offset):
    """
    utc_offset should be in the form '<+|->dd:dd'

    use verify_utc_offset to confirm before using this function
    """
    hours = int(utc_offset[0:3])
    minutes = int(utc_offset[4:])

    local_time = utc_time + timedelta(hours=hours, minutes=minutes)
    return local_time
