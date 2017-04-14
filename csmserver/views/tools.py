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
from flask import jsonify, render_template, request
from flask.ext.login import login_required, current_user

from database import DBSession

from models import logger
from models import CreateTarJob

from common import get_jump_host_list

from wtforms import Form
from wtforms import StringField
from wtforms.validators import Length, required

from utils import get_tarfile_file_list, get_file_list, untar, make_file_writable

from constants import get_repository_directory, get_temp_directory

from package_utils import is_external_file_a_smu
from package_utils import is_external_file_a_release_software

import os

tools = Blueprint('tools', __name__, url_prefix='/tools')


@tools.route('/hosts/')
@login_required
def host_list():
    return render_template('host/index.html')


@tools.route('/jump_hosts/')
@login_required
def jump_host_list():
    db_session = DBSession()

    hosts = get_jump_host_list(db_session)
    if hosts is None:
        abort(404)

    return render_template('jump_host/index.html', hosts=hosts)


@tools.route('/create_tar_file')
@login_required
def create_tar_file():
    create_tar_form = CreateTarForm(request.form)
    return render_template('tools/create_tar_file.html', form=create_tar_form)


@tools.route('/api/create_tar_job')
@login_required
def api_create_tar_job():
    db_session = DBSession()

    form = CreateTarForm(request.form)

    server_id = request.args.get('server_id')
    server_directory = request.args.get('server_directory')
    source_tars = request.args.getlist('source_tars[]')
    contents = request.args.getlist('tar_contents[]')
    additional_packages = request.args.getlist('additional_packages[]')
    new_tar_name = request.args.get('new_tar_name').replace('.tar', '')

    create_tar_job = CreateTarJob(
        server_id=server_id,
        server_directory=server_directory,
        source_tars=','.join(source_tars),
        contents=','.join(contents),
        additional_packages=','.join(additional_packages),
        new_tar_name=new_tar_name,
        created_by=current_user.username,
        status='Job Submitted.')

    db_session.add(create_tar_job)
    db_session.commit()

    job_id = create_tar_job.id

    return jsonify({'status': 'OK', 'job_id': job_id})


@tools.route('/api/get_progress')
@login_required
def get_progress():
    db_session = DBSession()
    job_id = request.args.get('job_id')

    tar_job = db_session.query(CreateTarJob).filter(CreateTarJob.id == job_id).first()
    if tar_job is None:
        logger.error('Unable to retrieve Create Tar Job: %s' % job_id)
        return jsonify(status='Unable to retrieve job')

    return jsonify(status='OK', progress=tar_job.status)


@tools.route('/api/get_tar_contents')
@login_required
def get_tar_contents():
    files = request.args.getlist('files[]')
    files = files[0].strip().split(',')
    rows = []
    repo_path = get_repository_directory()

    for file in files:
        if file:
            for f in get_tarfile_file_list(repo_path + file):
                row = {}
                row['file'] = repo_path + file + '/' + f
                row['filename'] = f
                row['source_tar'] = file
                rows.append(row)
    return jsonify(**{'data': rows})


@tools.route('/api/get_full_software_tar_files_from_csm_repository/')
@login_required
def get_full_software_tar_files_from_csm_repository():
    rows = []
    file_list = get_file_list(get_repository_directory())

    for filename in file_list:
        if is_external_file_a_release_software(filename):
            statinfo = os.stat(get_repository_directory() + filename)
            row = {}
            row['image_name'] = filename
            row['image_size'] = '{} bytes'.format(statinfo.st_size)
            rows.append(row)

    return jsonify(**{'data': rows})


@tools.route('/api/get_sp_files_from_csm_repository/')
@login_required
def get_sp_files_from_csm_repository():
    rows = []
    file_list = get_file_list(get_repository_directory())

    for filename in file_list:
        if is_external_file_a_smu(filename):
            statinfo = os.stat(get_repository_directory() + filename)
            row = {}
            row['image_name'] = filename
            row['image_size'] = '{} bytes'.format(statinfo.st_size)
            rows.append(row)

    return jsonify(**{'data': rows})


class CreateTarForm(Form):
    new_tar_name = StringField('New Tar File Name', [required(), Length(max=30)])
