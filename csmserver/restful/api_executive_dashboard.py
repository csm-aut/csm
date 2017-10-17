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
from flask import jsonify
from sqlalchemy import and_

from database import DBSession

from models import InstallJobHistory

from constants import JobStatus
from constants import InstallAction

from common import get_host
from common import get_host_list
from common import get_user_list
from common import get_host_platform_and_version_summary_tuples

from api_utils import validate_url_parameters

from api_constants import RESPONSE_ENVELOPE

KEY_HOSTNAME = 'hostname'
KEY_USERNAME = 'username'
KEY_CREATED_TIME = 'created_time'
KEY_CREATED_MONTH = 'created_month'
KEY_CREATED_YEAR = 'created_year'
KEY_SOFTWARE_PLATFORM = 'software_platform'
KEY_SOFTWARE_VERSION = 'software_version'
KEY_TOTAL_MONTHLY_INSTALLATIONS = 'total_monthly_installations'
KEY_INSTALL_ACTION_LIST = 'install_action_list'
KEY_INSTALL_ACTION_COUNTS = 'install_action_counts'
KEY_COUNT = 'count'


def api_get_monthly_host_enrollment_counts(request):
    """
    GET:
    http://localhost:5000/api/v1/executive_dashboard/api_get_monthly_host_enrollment_counts
    """

    rows = []
    counters = {}
    db_session = DBSession()

    hosts = get_host_list(db_session)

    for host in hosts:
        key = (host.created_time.year, host.created_time.month)
        if key in counters:
            counters[key] += 1
        else:
            counters[key] = 1

    for key, value in counters.items():
        row = dict()
        row[KEY_COUNT] = value
        row[KEY_CREATED_YEAR] = key[0]
        row[KEY_CREATED_MONTH] = key[1]
        rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {'counts': rows, 'total_hosts': len(hosts)}})


def api_get_monthly_user_enrollment_counts(request):
    """
    GET:
    http://localhost:5000/api/v1/executive_dashboard/get_monthly_user_enrollment_counts
    """

    rows = []
    counters = {}
    db_session = DBSession()

    users = get_user_list(db_session)

    for user in users:
        key = (user.created_time.year, user.created_time.month)
        if key in counters:
            counters[key] += 1
        else:
            counters[key] = 1

    for key, value in counters.items():
        row = dict()
        row[KEY_COUNT] = value
        row[KEY_CREATED_YEAR] = key[0]
        row[KEY_CREATED_MONTH] = key[1]
        rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {'counts': rows, 'total_users': len(users)}})


def api_get_host_platform_and_version_counts(request):
    """
    GET:
    http://localhost:5000/api/v1/executive_dashboard/get_host_platform_and_version_counts
    """
    db_session = DBSession()
    result_tuples = get_host_platform_and_version_summary_tuples(db_session)

    rows = []
    total_hosts = 0
    for result_tuple in result_tuples:
        row = dict()
        row[KEY_SOFTWARE_PLATFORM] = result_tuple[0]
        row[KEY_SOFTWARE_VERSION] = result_tuple[1]
        row[KEY_COUNT] = result_tuple[2]
        total_hosts += int(result_tuple[2])
        rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {'counts': rows, 'total_hosts': total_hosts}})


def api_get_monthly_installation_counts(request):
    """
    GET:
    http://localhost:5000/api/v1/executive_dashboard/get_monthly_installation_counts
    http://localhost:5000/api/v1/executive_dashboard/get_monthly_installation_counts?hostname=MyHost
    """
    validate_url_parameters(request, [KEY_HOSTNAME])

    rows = []
    counters = {}
    db_session = DBSession()
    install_action_list = [InstallAction.PRE_UPGRADE,
                           InstallAction.INSTALL_ADD,
                           InstallAction.INSTALL_ACTIVATE,
                           InstallAction.POST_UPGRADE,
                           InstallAction.INSTALL_COMMIT,
                           InstallAction.INSTALL_REMOVE,
                           InstallAction.INSTALL_REMOVE_ALL_INACTIVE,
                           InstallAction.INSTALL_DEACTIVATE,
                           InstallAction.MIGRATION_AUDIT,
                           InstallAction.PRE_MIGRATE,
                           InstallAction.MIGRATE_SYSTEM,
                           InstallAction.POST_MIGRATE,
                           InstallAction.FPD_UPGRADE,
                           InstallAction.SATELLITE_TRANSFER,
                           InstallAction.SATELLITE_ACTIVATE]

    clauses = [InstallJobHistory.status == JobStatus.COMPLETED]

    hostname = request.args.get(KEY_HOSTNAME)
    if hostname:
        host = get_host(db_session, hostname)
        if host is None:
            raise ValueError("Host '{}' does not exist in the database.".format(hostname))
        clauses.append(InstallJobHistory.host_id == host.id)

    install_jobs = db_session.query(InstallJobHistory).filter(and_(*clauses)).all()
    for install_job in install_jobs:
        # (2017, 4) : [10, 20, 15, and etc]
        key = (install_job.created_time.year, install_job.created_time.month)
        install_action = install_job.install_action

        if key not in counters:
            counters[key] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        try:
            index = install_action_list.index(install_action)
            if index > 0:
                counters[key][index] += 1
        except:
            pass

    for key, install_action_counts in counters.items():
        row = dict()
        row[KEY_INSTALL_ACTION_LIST] = install_action_list
        row[KEY_INSTALL_ACTION_COUNTS] = install_action_counts
        row[KEY_TOTAL_MONTHLY_INSTALLATIONS] = sum(install_action_counts)
        row[KEY_CREATED_YEAR] = key[0]
        row[KEY_CREATED_MONTH] = key[1]
        rows.append(row)

    return jsonify(**{RESPONSE_ENVELOPE: {'total_counts': rows, 'total_installations': len(install_jobs)}})
