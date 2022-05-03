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
from flask import render_template
from flask import request
from flask import jsonify
from flask import abort
from flask import send_file
from flask_login import login_required
from flask_login import current_user
from werkzeug.utils import safe_join
from database import DBSession

from models import Log
from models import SystemOption
from models import InstallJob
from models import DownloadJob
from models import InstallJobHistory
from models import InventoryJobHistory

from common import download_session_logs

from utils import is_empty
from utils import get_file_list
from utils import create_directory
from utils import create_temp_user_directory
from utils import make_file_writable

from filters import get_datetime_string

from constants import get_log_directory
from constants import get_csm_data_directory
from constants import get_doc_central_directory
from constants import InstallAction

import os
import io
import collections

log = Blueprint('log', __name__, url_prefix='/log')


@log.route('/logs/')
@login_required
def logs():
    return render_template('log.html', system_option=SystemOption.get(DBSession()))


@log.route('/api/get_system_logs/')
@login_required
def api_get_system_logs():
    db_session = DBSession()

    # Only shows the ERROR
    logs = db_session.query(Log).filter(
        Log.level == 'ERROR').order_by(Log.created_time.desc())

    rows = []
    for log in logs:
        row = {}
        row['id'] = log.id
        row['severity'] = log.level
        row['message'] = log.msg
        row['created_time'] = log.created_time
        rows.append(row)

    return jsonify(**{'data': rows})


@log.route('/api/logs/<int:log_id>/trace/')
@login_required
def api_get_log_trace(log_id):
    """
    Returns the log trace of a particular log record.
    """
    db_session = DBSession()

    log = db_session.query(Log).filter(Log.id == log_id).first()
    return jsonify(**{'data': [
        {'severity': log.level, 'message': log.msg,
            'trace': log.trace, 'created_time': log.created_time}
    ]})


@log.route('/download_system_logs')
@login_required
def download_system_logs():
    db_session = DBSession()
    logs = db_session.query(Log) \
        .order_by(Log.created_time.desc())

    contents = ''
    for log in logs:
        contents += get_datetime_string(log.created_time) + ' UTC\n'
        contents += log.level + ':' + log.msg + '\n'
        if log.trace is not None:
            contents += log.trace + '\n'
        contents += '-' * 70 + '\n'

    # Create a file which contains the size of the image file.
    temp_user_dir = create_temp_user_directory(current_user.username)
    log_file_path = os.path.normpath(
        os.path.join(temp_user_dir, "system_logs"))

    create_directory(log_file_path)
    make_file_writable(log_file_path)

    log_file = open(os.path.join(log_file_path, 'system_logs'), 'w')
    log_file.write(contents)
    log_file.close()

    return send_file(os.path.join(log_file_path, 'system_logs'), as_attachment=True)


# This route will prompt a file download
@log.route('/download_session_log')
@login_required
def download_session_log():
    return send_file(get_log_directory() + request.args.get('file_path'), as_attachment=True)


@log.route('/api/download_session_logs', methods=['POST'])
@login_required
def api_download_session_logs():
    file_list = request.args.getlist('file_list[]')[0].split(',')
    return download_session_logs(file_list, current_user.username)


@log.route('/api/get_session_log_file_diff')
@login_required
def api_get_session_log_file_diff():
    diff_file_path = request.args.get("diff_file_path")

    if is_empty(diff_file_path):
        return jsonify({'status': 'diff file is missing.'})

    file_diff_contents = ''
    with io.open(os.path.join(get_log_directory(), diff_file_path), "rt", encoding='latin-1') as fo:
        file_diff_contents = fo.read()

    data = [{'file_diff_contents': file_diff_contents}]

    return jsonify(**{'data': data})


@log.route('/hosts/<hostname>/<table>/session_log/<int:id>/')
@login_required
def host_session_log(hostname, table, id):
    """
    This route is also used by mailer.py for email notification.
    """
    db_session = DBSession()

    job = None
    doc_central_log_file_path = ''

    if table == 'install_job':
        job = db_session.query(InstallJob).filter(InstallJob.id == id).first()
    elif table == 'install_job_history':
        job = db_session.query(InstallJobHistory).filter(
            InstallJobHistory.id == id).first()

        doc_central_log_file_path = get_doc_central_log_path(job)
    elif table == 'inventory_job_history':
        job = db_session.query(InventoryJobHistory).filter(
            InventoryJobHistory.id == id).first()

    if job is None:
        abort(404)

    file_path = request.args.get('file_path')
    log_file_path = get_log_directory() + file_path

    if not(os.path.isdir(log_file_path) or os.path.isfile(log_file_path)):
        abort(404)

    file_pairs = {}
    log_file_contents = ''

    file_suffix = '.diff.html'
    if os.path.isdir(log_file_path):
        # Returns all files under the requested directory
        log_file_list = get_file_list(log_file_path)
        diff_file_list = [
            filename for filename in log_file_list if file_suffix in filename]

        for filename in log_file_list:
            diff_file_path = ''
            if file_suffix not in filename:
                if filename + file_suffix in diff_file_list:
                    diff_file_path = os.path.join(
                        file_path, filename + file_suffix)
                file_pairs[os.path.join(file_path, filename)] = diff_file_path

        file_pairs = collections.OrderedDict(sorted(file_pairs.items()))
    else:
        with io.open(log_file_path, "rt", encoding='latin-1') as fo:
            log_file_contents = fo.read()

    job_info = job.data.get('job_info')

    return render_template('host/session_log.html', hostname=hostname, table=table,
                           record_id=id, file_pairs=file_pairs,
                           log_file_contents=log_file_contents,
                           job_info=(
                               '' if job_info is None else '\n'.join(job_info)),
                           is_file=os.path.isfile(log_file_path),
                           doc_central_log_file_path=doc_central_log_file_path)


@log.route('/api/get_session_logs/table/<table>')
@login_required
def api_get_session_logs(table):
    id = request.args.get("record_id")

    db_session = DBSession()
    if table == 'install_job':
        install_job = db_session.query(InstallJob).filter(
            InstallJob.id == id).first()
    elif table == 'install_job_history':
        install_job = db_session.query(InstallJobHistory).filter(
            InstallJobHistory.id == id).first()
    elif table == 'inventory_job_history':
        install_job = db_session.query(InventoryJobHistory).filter(
            InventoryJobHistory.id == id).first()

    if install_job is None:
        abort(404)

    log_folder = install_job.session_log
    file_path = os.path.join(get_log_directory(), log_folder)

    if not os.path.isdir(file_path):
        abort(404)

    rows = []
    log_file_list = get_file_list(file_path)
    for file in log_file_list:
        row = dict()
        row['filepath'] = os.path.join(file_path, file)
        row['filename'] = file
        rows.append(row)

    return jsonify(**{'data': rows})


@log.route('/hosts/<hostname>/<table>/trace/<int:id>/')
@login_required
def host_trace(hostname, table, id):
    db_session = DBSession()

    trace = None
    if table == 'inventory_job_history':
        inventory_job = db_session.query(InventoryJobHistory).filter(
            InventoryJobHistory.id == id).first()
        trace = inventory_job.trace if inventory_job is not None else None
    elif table == 'install_job':
        install_job = db_session.query(InstallJob).filter(
            InstallJob.id == id).first()
        trace = install_job.trace if install_job is not None else None
    elif table == 'install_job_history':
        install_job = db_session.query(InstallJobHistory).filter(
            InstallJobHistory.id == id).first()
        trace = install_job.trace if install_job is not None else None
    elif table == 'download_job':
        download_job = db_session.query(DownloadJob).filter(
            DownloadJob.id == id).first()
        trace = download_job.trace if download_job is not None else None

    return render_template('host/trace.html', hostname=hostname, trace=trace)


# This route will prompt a file download
@log.route('/download_doc_central_log')
@login_required
def download_doc_central_log():
    return send_file(safe_join(get_doc_central_directory(), request.args.get('file_path')), as_attachment=True)


def get_doc_central_log_path(install_job):
    """
    This method is used to support SIT Doc Central feature
    :param install_job: must be an install job history instance
    :return: The aggregated path
    """
    doc_central_log_file_path = ''
    if install_job.install_action == InstallAction.POST_UPGRADE and not is_empty(install_job.load_data('doc_central_log_file_path')):
        path = os.path.join(get_doc_central_directory(),
                            install_job.load_data('doc_central_log_file_path'))
        if os.path.isfile(path):
            doc_central_log_file_path = path

    return doc_central_log_file_path
