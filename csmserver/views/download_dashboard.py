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
from flask import jsonify
from flask import render_template

from flask.ext.login import login_required
from flask.ext.login import current_user

from database import DBSession

from common import can_install
from common import can_delete_install
from common import get_server_by_id

from models import logger
from models import SystemOption
from models import DownloadJob
from models import DownloadJobHistory

from constants import UNKNOWN
from constants import JobStatus
from constants import UserPrivilege
from constants import get_repository_directory

from utils import is_empty
from utils import get_file_list
from utils import get_tarfile_file_list
from utils import datetime_from_local_to_utc

from tarfile import ReadError

import os
import datetime

download_dashboard = Blueprint('download_dashboard', __name__, url_prefix='/download_dashboard')


@download_dashboard.route('/')
@login_required
def home():
    if not can_install(current_user):
        abort(401)

    return render_template('host/download_dashboard.html', system_option=SystemOption.get(DBSession()))


def get_download_job_json_dict(db_session, download_jobs):
    rows = []
    for download_job in download_jobs:
        if isinstance(download_job, DownloadJob) or isinstance(download_job, DownloadJobHistory):
            row = dict()
            row['download_job_id'] = download_job.id
            row['image_name'] = download_job.cco_filename
            row['scheduled_time'] = download_job.scheduled_time

            server = get_server_by_id(db_session, download_job.server_id)
            if server is not None:
                row['server_repository'] = server.hostname
                if not is_empty(download_job.server_directory):
                    row['server_repository'] = row['server_repository'] + \
                                               '<br><span style="color: Gray;"><b>Sub-directory:</b></span> ' + \
                                               download_job.server_directory
            else:
                row['server_repository'] = UNKNOWN

            row['status'] = download_job.status
            row['status_time'] = download_job.status_time
            row['created_by'] = download_job.created_by

            if download_job.trace is not None:
                row['trace'] = download_job.id

            rows.append(row)

    return {'data': rows}


@download_dashboard.route('/api/get_files_from_csm_repository/')
@login_required
def api_get_files_from_csm_repository():
    rows = []
    file_list = get_file_list(get_repository_directory())

    for filename in file_list:
        if filename.endswith('.tar'):
            statinfo = os.stat(get_repository_directory() + filename)
            row = dict()
            row['image_name'] = filename
            row['image_size'] = str(statinfo.st_size)
            row['downloaded_time'] = datetime_from_local_to_utc(datetime.datetime.fromtimestamp(statinfo.st_mtime))
            rows.append(row)

    return jsonify(**{'data': rows})


@download_dashboard.route('/api/image/<image_name>/delete/', methods=['DELETE'])
@login_required
def api_delete_image_from_repository(image_name):
    if current_user.privilege != UserPrivilege.ADMIN and current_user.privilege != UserPrivilege.NETWORK_ADMIN:
        abort(401)

    tar_image_path = get_repository_directory() + image_name
    try:
        file_list = get_tarfile_file_list(tar_image_path)
        for filename in file_list:
            try:
                os.remove(get_repository_directory() + filename)
            except:
                pass
    except ReadError:
        # In case, it is a partial downloaded TAR.
        pass

    try:
        os.remove(tar_image_path)
        os.remove(tar_image_path + '.size')
    except:
        logger.exception('api_delete_image_from_repository() hit exception')
        return jsonify({'status': 'Failed'})

    return jsonify({'status': 'OK'})


@download_dashboard.route('/hosts/delete_all_failed_downloads/', methods=['DELETE'])
@login_required
def delete_all_failed_downloads():
    if not can_delete_install(current_user):
        abort(401)

    return delete_all_downloads(status=JobStatus.FAILED)


@download_dashboard.route('/hosts/delete_all_scheduled_downloads/', methods=['DELETE'])
@login_required
def delete_all_scheduled_downloads():
    if not can_delete_install(current_user):
        abort(401)

    return delete_all_downloads()


def delete_all_downloads(status=None):
    db_session = DBSession()

    try:
        download_jobs = db_session.query(DownloadJob).filter(DownloadJob.status == status)
        for download_job in download_jobs:
            db_session.delete(download_job)

        db_session.commit()

        return jsonify({'status': 'OK'})
    except:
        logger.exception('delete_download_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@download_dashboard.route('/delete_download_job/<int:id>/', methods=['DELETE'])
@login_required
def delete_download_job(id):
    if not can_delete_install(current_user):
        abort(401)

    db_session = DBSession()

    download_job = db_session.query(DownloadJob).filter(DownloadJob.id == id).first()
    if download_job is None:
        abort(404)

    try:
        # Download jobs that are in progress cannot be deleted.
        if download_job.status is None or download_job.status == JobStatus.FAILED:
            db_session.delete(download_job)
            db_session.commit()

        return jsonify({'status': 'OK'})

    except:
        logger.exception('delete_download_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})


@download_dashboard.route('/resubmit_download_job/<int:id>/', methods=['POST'])
@login_required
def resubmit_download_job(id):
    if not can_install(current_user):
        abort(401)

    db_session = DBSession()

    download_job = db_session.query(DownloadJob).filter(DownloadJob.id == id).first()
    if download_job is None:
        abort(404)

    try:
        # Download jobs that are in progress cannot be deleted.
        download_job.status = None
        download_job.status_time = None
        db_session.commit()

        return jsonify({'status': 'OK'})

    except:
        logger.exception('resubmit_download_job() hit exception')
        return jsonify({'status': 'Failed: check system logs for details'})
