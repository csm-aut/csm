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
from api_utils import RECORDS_PER_PAGE
from api_utils import get_total_pages

from utils import is_empty

from sqlalchemy import and_

from database import DBSession

from models import InstallJob
from models import InstallJobHistory

from constants import get_log_directory

from common import delete_install_job_dependencies
from common import create_or_update_install_job
from common import get_server
from common import get_server_by_id
from common import get_host
from common import get_host_by_id
from common import download_session_logs

from views.custom_command import get_command_profile, get_command_profile_by_id

from datetime import datetime, timedelta
from operator import itemgetter

import re
import os

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
                "install_request_list": [ {"status": "SUCCESS", "hostname": "My Host", "install_request_id": 101},
                               {"status": "FAILED", "hostname": "My Host 2", "status_message": "Unable to locate host"} ]

                }
            }
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
    for r in json_data:
        row = {}
        try:
            if 'scheduled_time' not in r.keys():
                #row[STATUS] = APIStatus.FAILED
                #row[STATUS_MESSAGE] = 'Missing scheduled_time.'
                #valid_request = False
                row['utc_scheduled_time'] = datetime.utcnow() #TODO: convert to UTC time....
            elif 'utc_offset' not in r.keys():
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = 'Missing utc_offset.'
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
            return jsonify(**{ENVELOPE: {'install_request_list': rows}}), 400

        if STATUS not in row.keys():
            if 'hostname' not in r.keys():
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = 'Missing hostname.'
                valid_request = False
            elif not get_host(db_session, r['hostname']):
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = 'Invalid hostname.'
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

    if not valid_request:
        for r in rows:
            if STATUS not in r.keys():
                r[STATUS] = APIStatus.FAILED
                r[STATUS_MESSAGE] = 'Not submitted. Check other jobs for error message.'
            if 'utc_scheduled_time' in r.keys():
                r.pop('utc_scheduled_time')
        return jsonify(**{ENVELOPE: {'install_request_list': rows}}), 400


    # Sort on install_action, then hostname, then scheduled_time
    json_data = sorted(rows, cmp=getKey)
    json_data = sorted(json_data, key=itemgetter('utc_scheduled_time', 'hostname'))

    print json_data

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
        return jsonify(**{ENVELOPE: {'install_request_list': rows}})


    # For implicit dependencies
    dependency_list = {}
    order = ['Pre-Upgrade', 'Add', 'Activate', 'Post-Upgrade', 'Commit', 'Remove', 'Deactivate']

    rows = []
    for install_request in install_requests:
        row = {}
        msg = ''
        # If dependency was not specified, there may be an implicit dependency
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
                command_profile = get_command_profile(db_session, install_request['command_profile']).id
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

        rows.append(row)
    return jsonify(**{ENVELOPE: {'install_request_list': rows}})


def api_get_install_request(request):
    """
    GET:
    http://localhost:5000/api/v1/install
    http://localhost:5000/api/v1/install?id=1
    http://localhost:5000/api/v1/install?hostname=R1
    http://localhost:5000/api/v1/install?hostname=r1&install_action=Add
    http://localhost:5000/api/v1/install?hostname=R1&status="failed"
    """
    rows = []
    db_session = DBSession
    try:
        page = int(request.args.get('page')) if request.args.get('page') else 1
        if page <= 0: page = 1
    except ValueError:
        return jsonify(**{ENVELOPE: 'Unknown page number'}), 400

    clauses = []

    utc_offset = request.args.get('utc_offset')
    id = request.args.get('id')
    if id:
        install_jobs = db_session.query(InstallJob).filter(
            (InstallJob.id==id))
    else:
        hostname = request.args.get('hostname')
        if hostname:
            host = get_host(db_session, hostname)
            if host:
                host_id = host.id
            else:
                return jsonify(**{ENVELOPE: 'Invalid hostname: %s.' % hostname}), 400
            clauses.append(InstallJob.host_id == host_id)

        install_action = request.args.get('install_action')
        if install_action:
            clauses.append(InstallJob.install_action == install_action)

        status = request.args.get('status')
        if status:
            if status == 'scheduled':
                clauses.append(InstallJob.status.is_(None))
            elif status == 'in-progress': # get all the jobs, then code filter for status (Test first)
                clauses.append(InstallJob.status != None)
                clauses.append(InstallJob.status != 'failed')
                clauses.append(InstallJob.status != 'completed')
            else:
                clauses.append(InstallJob.status == status)


        scheduled_time = request.args.get('scheduled_time')
        if scheduled_time:
            if not utc_offset:
                return jsonify(**{ENVELOPE: 'utc_offset must be specified if scheduled_time is specified.'})
            elif not verify_utc_offset(utc_offset):
                return jsonify(**{
                    ENVELOPE: "Invalid utc_offset: Must be in '<+|->dd:dd' format and be between -12:00 and +14:00."})
            try:
                time = datetime.strptime(scheduled_time, "%m-%d-%Y-%I:%M-%p")
                time_utc = get_utc_time(time, utc_offset)
                clauses.append(InstallJob.scheduled_time >= time_utc)
            except ValueError:
                return jsonify(**{
                    ENVELOPE: "Invalid scheduled_time: %s must be in 'mm-dd-yyyy hh:mm AM|PM' format." % time})

        install_jobs = get_install_jobs_by_page(db_session, clauses, page)

    if is_empty(install_jobs):
        return jsonify(**{
            ENVELOPE: "No install jobs fit the given criteria."})

    for install_job in install_jobs:
        row = {}
        row['id'] = install_job.id
        row['install_action'] = install_job.install_action
        row['dependency'] = install_job.dependency

        if install_job.server_id:
            server = get_server_by_id(db_session, install_job.server_id)
            row['server_repository'] = server.hostname
        else:
            row['server_repository'] = None

        if utc_offset and verify_utc_offset(utc_offset):
            if install_job.scheduled_time:
                row['scheduled_time'] = get_local_time(install_job.scheduled_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")
            if install_job.start_time:
                row['start_time'] = get_local_time(install_job.start_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")
            if install_job.status_time:
                row['status_time'] = get_local_time(install_job.status_time, utc_offset).strftime("%m-%d-%Y %I:%M %p")

        else:
            row['scheduled_time'] = install_job.scheduled_time
            row['start_time'] = install_job.start_time
            row['status_time'] = install_job.status_time

        row['server_directory'] = install_job.server_directory
        row['packages'] = install_job.packages
        row['pending_downloads'] = install_job.pending_downloads
        row['status'] = install_job.status
        row['trace'] = install_job.trace
        row['created_by'] = install_job.created_by
        row['hostname'] = get_host_by_id(db_session, install_job.host_id).hostname

        if not is_empty(install_job.custom_command_profile_id) and int(install_job.custom_command_profile_id) > 0:
            row['custom_command_profile'] = get_command_profile_by_id(db_session,
                                                                  install_job.custom_command_profile_id).profile_name
        else:
            row['custom_command_profile'] = 'None'

        rows.append(row)

    total_pages = get_total_pages(db_session, InstallJob, clauses)

    return jsonify(**{ENVELOPE: {'install_job_list': rows}, 'current_page': page, 'total_pages': total_pages})


def api_delete_install_job(request):
    rows = []
    db_session = DBSession
    clauses = []

    id = request.args.get('id')
    if id:
        install_jobs = db_session.query(InstallJob).filter(
            (InstallJob.id == id))
    else:
        hostname = request.args.get('hostname')
        if hostname:
            host_id = get_host(db_session, hostname).id
            clauses.append(InstallJob.host_id == host_id)

        status = request.args.get('status')
        if status:
            if status not in ['failed', 'scheduled']:
                return jsonify(**{ENVELOPE: "Invalid value for status: must be 'failed' or 'scheduled'."})
            else:
                if status == "scheduled":
                    db_status = None
                else:
                    db_status = status
                clauses.append(InstallJob.status == db_status)

        install_jobs = get_install_jobs_by_page(db_session, clauses, 1)

    ids = set()
    for install_job in install_jobs:
        row = {}
        # Install jobs that are in progress cannot be deleted.
        if install_job.status in ['failed', 'completed', None]:
            row['id'] = install_job.id

            try:
                db_session.delete(install_job)
                db_session.commit()
                row[STATUS] = APIStatus.SUCCESS
                ids.add(install_job.id)
            except:
                row[STATUS] = APIStatus.FAILED
                row[STATUS_MESSAGE] = "Failed to delete install job."
        else:
            row['id'] = install_job.id
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = 'Cannot delete in-progress jobs.'

        rows.append(row)

    for id in ids:
        try:
            deleted = delete_install_job_dependencies(db_session, id)
            db_session.commit()

            for job in deleted:
                row = {}
                row['id'] = job
                row[STATUS] = APIStatus.SUCCESS
                rows.append(row)

        except:
            row[STATUS] = APIStatus.FAILED
            row[STATUS_MESSAGE] = "Failed to delete some or all dependent jobs."

    return jsonify(**{ENVELOPE: {'install_job_list': rows}})


def api_get_session_log(id):
    db_session = DBSession

    if not id:
        return jsonify(**{ENVELOPE: "ID must be specified."})

    install_job = db_session.query(InstallJob).filter((InstallJob.id == id)).first()
    if install_job is None:
        install_job = db_session.query(InstallJobHistory).filter((InstallJobHistory.id == id)).first()
    if install_job is None:
        return jsonify(**{ENVELOPE: "Invalid id."})

    if install_job.session_log is not None:
        log_dir = os.path.join(get_log_directory(), install_job.session_log)
        file_list = [os.path.join(log_dir, f) for f in os.listdir(log_dir)]
        return download_session_logs(file_list)
    else:
        return jsonify(**{ENVELOPE: "No log files."})


def get_install_jobs_by_page(db_session, clauses, page):
    if not is_empty(clauses):
        return db_session.query(InstallJob).filter(and_(*clauses)).\
            order_by(InstallJob.id.asc()).slice((page - 1) * RECORDS_PER_PAGE, page * RECORDS_PER_PAGE)
    else:
        return db_session.query(InstallJob).order_by(InstallJob.id.asc()) \
            .slice((page - 1) * RECORDS_PER_PAGE, page * RECORDS_PER_PAGE)


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
                        return 0, 'Prerequisite job scheduled time is later than %s.' % install_request['scheduled_time']
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
        if not get_command_profile(db_session, install_request['command_profile']):
            return False, "Invalid value for command_profile; profile must exist."

    return True, "valid"


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
