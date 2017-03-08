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
from flask import g

from api_utils import validate_url_parameters
from api_utils import convert_value_to_list
from api_utils import validate_required_keys_in_dict
from api_utils import validate_acceptable_keys_in_dict
from api_utils import convert_json_request_to_list

from api_constants import HTTP_OK
from api_constants import HTTP_BAD_REQUEST
from api_constants import HTTP_MULTI_STATUS_ERROR

from api_constants import RESPONSE_ENVELOPE
from api_constants import RESPONSE_STATUS
from api_constants import RESPONSE_STATUS_MESSAGE
from api_constants import RESPONSE_TRACE
from api_constants import APIStatus

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
from common import get_custom_command_profile_by_id
from common import get_custom_command_profile_name_to_id_dict

from datetime import datetime, timedelta

import re
import os
import traceback

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

acceptable_keys = [KEY_HOSTNAME, KEY_INSTALL_ACTION, KEY_SCHEDULED_TIME, KEY_UTC_OFFSET, KEY_CUSTOM_COMMAND_PROFILE,
                   KEY_DEPENDENCY, KEY_SERVER_REPOSITORY, KEY_SERVER_DIRECTORY, KEY_SOFTWARE_PACKAGES]

required_keys_dict = {InstallAction.PRE_UPGRADE: [KEY_HOSTNAME],
                      InstallAction.INSTALL_ADD: [KEY_HOSTNAME, KEY_SERVER_REPOSITORY, KEY_SOFTWARE_PACKAGES],
                      InstallAction.INSTALL_ACTIVATE: [KEY_HOSTNAME, KEY_SOFTWARE_PACKAGES],
                      InstallAction.POST_UPGRADE: [KEY_HOSTNAME],
                      InstallAction.INSTALL_COMMIT: [KEY_HOSTNAME],
                      InstallAction.INSTALL_REMOVE: [KEY_HOSTNAME, KEY_SOFTWARE_PACKAGES],
                      InstallAction.INSTALL_DEACTIVATE: [KEY_HOSTNAME, KEY_SOFTWARE_PACKAGES]}

ordered_install_actions = [InstallAction.PRE_UPGRADE, InstallAction.INSTALL_ADD,
                           InstallAction.INSTALL_ACTIVATE, InstallAction.POST_UPGRADE,
                           InstallAction.INSTALL_COMMIT]

# Supported install actions
supported_install_actions = ordered_install_actions + [InstallAction.INSTALL_REMOVE,
                                                       InstallAction.INSTALL_DEACTIVATE]


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
               'software_packages': ['asr9k-px-5.3.3.CSCuz05961.pie, asr9k-px-5.3.3.CSCux89921.pie],
               'dependency': 'Pre-Upgrade'} ]

    Install Action: Activate, Remove, Deactivate
        BODY:
            [ {'hostname': 'My Host',
               'install_action': 'Activate',
               'scheduled_time': '05-02-2016 08:00 AM',
               'software_packages': ['asr9k-px-5.3.3.CSCuz05961.pie, asr9k-px-5.3.3.CSCux89921.pie]
               'dependency': '101'} ]


        RETURN:
            {"api_response": {
                "install_job_list": [ {"status": "SUCCESS", "hostname": "My Host", "id": 101},
                                      {"status": "FAILED", "hostname": "My Host 2", "status_message": "Unable to locate host"} ]

                }
            }
    """
    rows = []
    error_found = False
    db_session = DBSession()
    custom_command_profile_dict = get_custom_command_profile_name_to_id_dict(db_session)
    # ----------------------------  first phase is to attempt the data validation ---------------------------- #

    entries = []
    json_list = convert_json_request_to_list(request)

    for data in json_list:
        row = dict()
        try:
            validate_required_keys_in_dict(data, [KEY_INSTALL_ACTION])

            install_action = data[KEY_INSTALL_ACTION]
            if install_action not in supported_install_actions:
                raise ValueError("'{}' is an invalid install action.".format(install_action))

            validate_acceptable_keys_in_dict(data, acceptable_keys)
            validate_required_keys_in_dict(data, required_keys_dict[install_action])

            hostname = data[KEY_HOSTNAME]
            host = get_host(db_session, hostname)
            if host is None:
                raise ValueError("'{}' is an invalid hostname.".format(data[KEY_HOSTNAME]))

            if KEY_SERVER_REPOSITORY in data.keys():
                server = get_server(db_session, data[KEY_SERVER_REPOSITORY])
                if server is None:
                    raise ValueError("'{}' is an invalid server repository.".format(data[KEY_SERVER_REPOSITORY]))

            if KEY_CUSTOM_COMMAND_PROFILE in data.keys():
                custom_command_profile_names = convert_value_to_list(data, KEY_CUSTOM_COMMAND_PROFILE)
                for custom_command_profile_name in custom_command_profile_names:
                    custom_command_profile_id = custom_command_profile_dict.get(custom_command_profile_name)
                    if custom_command_profile_id is None:
                        raise ValueError("'{}' is an invalid custom command profile.".format(custom_command_profile_name))

            if KEY_SOFTWARE_PACKAGES in data.keys() and is_empty(data[KEY_SOFTWARE_PACKAGES]):
                raise ValueError("Software packages when specified cannot be empty.")

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
            row[RESPONSE_STATUS] = APIStatus.FAILED
            row[RESPONSE_STATUS_MESSAGE] = e.message
            error_found = True

        # Add the original key value pairs to the new array.
        for key in data.keys():
            row[key] = data[key]

        rows.append(row)

    # End of loop

    if error_found:
        for row in rows:
            if RESPONSE_STATUS not in row.keys():
                row[RESPONSE_STATUS] = APIStatus.FAILED
                row[RESPONSE_STATUS_MESSAGE] = 'Not submitted. Check other jobs for error message.'

            if KEY_UTC_SCHEDULED_TIME in row.keys():
                row.pop(KEY_UTC_SCHEDULED_TIME)

        return jsonify(**{RESPONSE_ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), HTTP_BAD_REQUEST

    # ----------------------------  Second phase is to attempt the job creation ---------------------------- #

    sorted_list = sorted(rows, cmp=get_key)

    rows = []
    error_found = False
    implicit_dependency_list = {}

    for install_request in sorted_list:
        row = dict()
        try:
            hostname = install_request[KEY_HOSTNAME]
            install_action = install_request[KEY_INSTALL_ACTION]

            row[KEY_INSTALL_ACTION] = install_action
            row[KEY_HOSTNAME] = hostname

            host_id = get_host(db_session, hostname).id
            utc_scheduled_time = install_request[KEY_UTC_SCHEDULED_TIME].strftime("%m/%d/%Y %I:%M %p")

            server_id = -1
            if KEY_SERVER_REPOSITORY in install_request.keys():
                server = get_server(db_session, install_request[KEY_SERVER_REPOSITORY])
                if server is not None:
                    server_id = server.id

            server_directory = ''
            if KEY_SERVER_DIRECTORY in install_request.keys():
                server_directory = install_request[KEY_SERVER_DIRECTORY]

            software_packages = []
            if KEY_SOFTWARE_PACKAGES in install_request.keys():
                software_packages = install_request[KEY_SOFTWARE_PACKAGES]

            custom_command_profile_ids = []
            if KEY_CUSTOM_COMMAND_PROFILE in install_request.keys():
                custom_command_profile_names = convert_value_to_list(install_request, KEY_CUSTOM_COMMAND_PROFILE)
                for custom_command_profile_name in custom_command_profile_names:
                    custom_command_profile_id = custom_command_profile_dict.get(custom_command_profile_name)
                    if custom_command_profile_id is not None:
                        custom_command_profile_ids.append(str(custom_command_profile_id))

            install_job = create_or_update_install_job(db_session,
                                                       host_id=host_id,
                                                       install_action=install_action,
                                                       scheduled_time=utc_scheduled_time,
                                                       software_packages=software_packages,
                                                       server_id=server_id,
                                                       server_directory=server_directory,
                                                       custom_command_profile_ids=custom_command_profile_ids,
                                                       dependency=get_dependency_id(db_session, implicit_dependency_list, install_request, host_id),
                                                       created_by=g.api_user.username)

            row[KEY_ID] = install_job.id

            if install_action in ordered_install_actions:
                if hostname not in implicit_dependency_list:
                    implicit_dependency_list[hostname] = []

                implicit_dependency_list[hostname].append((install_job.id, install_action))

            row[RESPONSE_STATUS] = APIStatus.SUCCESS

        except Exception as e:
            row[RESPONSE_STATUS] = APIStatus.FAILED
            row[RESPONSE_STATUS_MESSAGE] = e.message
            row[RESPONSE_TRACE] = traceback.format_exc()
            error_found = True

        rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def get_key(dict1, dict2):
    key1 = "{}{}".format(dict1[KEY_HOSTNAME], str(supported_install_actions.index(dict1[KEY_INSTALL_ACTION])).zfill(2))
    key2 = "{}{}".format(dict2[KEY_HOSTNAME], str(supported_install_actions.index(dict2[KEY_INSTALL_ACTION])).zfill(2))

    return cmp(key1, key2)


def get_dependency_id(db_session, implicit_dependency_list, install_request, host_id):
    hostname = install_request[KEY_HOSTNAME]
    install_action = install_request[KEY_INSTALL_ACTION]
    utc_scheduled_time = install_request[KEY_UTC_SCHEDULED_TIME]

    if KEY_DEPENDENCY in install_request.keys():
        dependency = install_request[KEY_DEPENDENCY]
        if dependency.isdigit():
            install_job = db_session.query(InstallJob).filter(InstallJob.id == int(dependency)).first()
            if install_job:
                if install_job.host_id != host_id:
                    raise ValueError("The dependency '{}' requested belongs to a different host.".format(dependency))
                elif install_job.scheduled_time > install_request[KEY_UTC_SCHEDULED_TIME]:
                    raise ValueError("The dependency '{}' requested has a later scheduled time.".format(dependency))
                else:
                    return int(dependency)
            else:
                raise ValueError("Dependency '{}' does not exist in the database.".format(dependency))
        else:
            # dependency is specified as an install action string.
            if hostname in implicit_dependency_list.keys():
                for id, action in implicit_dependency_list[hostname]:
                    if action == dependency:
                        return id

            # Check the database since the hostname and install action are not found in the cache.
            install_jobs = db_session.query(InstallJob).filter(and_(InstallJob.host_id == host_id,
                                                                    InstallJob.install_action == dependency)).order_by(InstallJob.scheduled_time.desc())
            for install_job in install_jobs:
                if install_job.scheduled_time <= utc_scheduled_time:
                    return install_job.id

            raise ValueError("'{}' is an invalid dependency.".format(dependency))

    else:
        # Check to see if implicit dependency needs to be applied here.
        if install_action in ordered_install_actions and hostname in implicit_dependency_list.keys():
            last_id, last_action = implicit_dependency_list[hostname][-1]

            if ordered_install_actions.index(last_action) < ordered_install_actions.index(install_action):
                return last_id

    return 0


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
            row[RESPONSE_STATUS] = APIStatus.FAILED
            row[RESPONSE_STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


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
            row[KEY_SCHEDULED_TIME] = get_local_time(install_job.scheduled_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")
        else:
            row[KEY_SCHEDULED_TIME] = ""

        if install_job.start_time:
            row[KEY_START_TIME] = get_local_time(install_job.start_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")
        else:
            row[KEY_START_TIME] = ""

        if install_job.status_time:
            row[KEY_STATUS_TIME] = get_local_time(install_job.status_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")
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
            raise ValueError("Install job id '{}' does not exist in the database.".format(id))
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

                row[RESPONSE_STATUS] = APIStatus.SUCCESS
            else:
                raise ValueError("Unable to delete install job '{}' as it is in progress.".format(install_job.id))

        except Exception as e:
            row[RESPONSE_STATUS] = APIStatus.FAILED
            row[RESPONSE_STATUS_MESSAGE] = e.message
            error_found = True

        rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {KEY_INSTALL_JOB_LIST: rows}}), (HTTP_OK if not error_found else HTTP_MULTI_STATUS_ERROR)


def api_get_session_log(id):
    db_session = DBSession

    if not id:
        raise ValueError("Install job id must be specified.")

    install_job = db_session.query(InstallJob).filter((InstallJob.id == id)).first()
    if install_job is None:
        install_job = db_session.query(InstallJobHistory).filter((InstallJobHistory.install_job_id == id)).first()

    if install_job is None:
        raise ValueError("Install job id '%d' does not exist in the database." % id)

    if install_job.session_log is not None:
        log_dir = os.path.join(get_log_directory(), install_job.session_log)
        file_list = [os.path.join(log_dir, f) for f in os.listdir(log_dir)]

        return download_session_logs(file_list)
    else:
        raise ValueError("Session log does not exist for install job id '%d'." % id)


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
