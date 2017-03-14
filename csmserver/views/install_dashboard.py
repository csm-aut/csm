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
from flask import jsonify
from flask import abort
from flask import render_template
from flask import url_for
from flask import request
from flask.ext.login import current_user

from sqlalchemy import and_

from database import DBSession

from models import logger
from models import SystemOption
from models import InstallJob
from models import DownloadJob
from models import InstallJobHistory
from models import get_download_job_key_dict

from common import get_download_job_key
from common import delete_install_job_dependencies
from common import can_delete_install
from common import can_install

from constants import JobStatus


from flask.ext.login import login_required

install_dashboard = Blueprint('install_dashboard', __name__, url_prefix='/install_dashboard')


@install_dashboard.route('/')
@login_required
def home():
    return render_template('host/install_dashboard.html', system_option=SystemOption.get(DBSession()))


@install_dashboard.route('/api/install_dashboard/cookie')
@login_required
def api_get_install_dashboard_cookie():
    system_option = SystemOption.get(DBSession())

    return jsonify(**{'data': [{'can_schedule': system_option.can_schedule, 'can_install': system_option.can_install}]})


@install_dashboard.route('/api/delete_all_failed_installations/', methods=['DELETE'])
@login_required
def api_delete_all_failed_installations():
    if not can_delete_install(current_user):
        abort(401)

    return delete_all_installations(status=JobStatus.FAILED)


@install_dashboard.route('/api/delete_all_scheduled_installations/', methods=['DELETE'])
@login_required
def api_delete_all_scheduled_installations():
    if not can_delete_install(current_user):
        abort(401)

    return delete_all_installations()


def delete_all_installations(status=JobStatus.SCHEDULED):
    db_session = DBSession()

    try:
        install_jobs = db_session.query(InstallJob).filter(InstallJob.status == status)
        for install_job in install_jobs:
            db_session.delete(install_job)

            if status == JobStatus.FAILED:
                delete_install_job_dependencies(db_session, install_job.id)

        db_session.commit()

        return jsonify({'status': 'OK'})
    except:
        logger.exception('delete_install_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@install_dashboard.route('/api/hosts/install/delete/<int:id>/', methods=['DELETE'])
@login_required
def api_delete_install_job(id):
    if not can_delete_install(current_user):
        abort(401)

    db_session = DBSession()

    install_job = db_session.query(InstallJob).filter(InstallJob.id == id).first()
    if install_job is None:
        abort(404)

    try:
        # Install jobs that are in progress cannot be deleted.
        if install_job.status in [JobStatus.SCHEDULED, JobStatus.FAILED]:
            db_session.delete(install_job)

        delete_install_job_dependencies(db_session, install_job.id)

        db_session.commit()

        return jsonify({'status': 'OK'})

    except:
        logger.exception('delete_install_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


def get_download_job_status(download_job_key_dict, install_job, dependency_status):
    num_pending_downloads = 0
    num_failed_downloads = 0
    is_pending_download = False

    pending_downloads = install_job.pending_downloads.split(',')
    for filename in pending_downloads:
        download_job_key = get_download_job_key(install_job.user_id, filename, install_job.server_id, install_job.server_directory)
        if download_job_key in download_job_key_dict:
            download_job = download_job_key_dict[download_job_key]
            if download_job.status == JobStatus.FAILED:
                num_failed_downloads += 1
            else:
                num_pending_downloads += 1
            is_pending_download = True

    if is_pending_download:
        job_status = "({} pending".format(num_pending_downloads)
        if num_failed_downloads > 0:
            job_status = "{},{} failed)".format(job_status, num_failed_downloads)
        else:
            job_status = "{})".format(job_status)

        # job_status = '(Failed)' if is_download_failed else ''
        download_url = '<a href="' + url_for('download_dashboard.home') + '">Pending Download ' + job_status + '</a>'
        if len(dependency_status) > 0:
            dependency_status = '{}<br/>{}'.format(dependency_status, download_url)
        else:
            dependency_status = download_url

    return dependency_status


def get_install_job_json_dict(install_jobs):
    """
    install_jobs is a list of install_job instances from the install_job or install_job_history table.
    Schema in the install_job_history table is a superset of the install_job table.
    """
    download_job_key_dict = get_download_job_key_dict()
    rows = []
    for install_job in install_jobs:
        if isinstance(install_job, InstallJob) or isinstance(install_job, InstallJobHistory):
            row = dict()
            row['install_job_id'] = install_job.id
            row['hostname'] = install_job.host.hostname
            row['dependency'] = '' if install_job.dependency is None else 'Another Installation'
            row['install_action'] = install_job.install_action
            row['scheduled_time'] = install_job.scheduled_time

            # Retrieve the pending download status of the scheduled download job.
            # The install job has not been started if its status is None.
            if install_job.status is None:
                row['dependency'] = get_download_job_status(download_job_key_dict, install_job, row['dependency'])

            row['start_time'] = install_job.start_time
            row['packages'] = install_job.packages

            if isinstance(install_job, InstallJob):
                row['server_id'] = install_job.server_id
                row['server_directory'] = install_job.server_directory
                row['user_id'] = install_job.user_id

            if install_job.status == JobStatus.IN_PROGRESS:
                row['status'] = install_job.status_message
            else:
                row['status'] = install_job.status

            row['status_time'] = install_job.status_time
            row['created_by'] = install_job.created_by

            if install_job.session_log is not None:
                row['session_log'] = install_job.session_log

            if install_job.trace is not None:
                row['trace'] = install_job.id

            rows.append(row)

    return {'data': rows}


@install_dashboard.route('/api/resubmit_download_jobs/')
@login_required
def api_resubmit_download_jobs():
    if not can_install(current_user):
        abort(401)

    user_id = request.args.get("user_id")
    server_id = request.args.get("server_id")
    server_directory = request.args.get("server_directory")

    db_session = DBSession()
    download_jobs = db_session.query(DownloadJob).filter(and_(DownloadJob.user_id == user_id,
        DownloadJob.server_id == server_id, DownloadJob.server_directory == server_directory))

    for download_job in download_jobs:
        download_job.status = None
        download_job.status_time = None
    db_session.commit()

    return jsonify({'status': 'OK'})
