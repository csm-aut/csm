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
from flask import jsonify, render_template, request
from flask.ext.login import login_required, current_user

from database import DBSession

from models import Server
from models import logger
from models import CreateTarJob

from wtforms import Form
from wtforms import StringField
from wtforms.validators import Length, required

from forms import SelectServerForm

from server_helper import get_server_impl

from utils import get_tarfile_file_list, get_file_list, untar, make_file_writable

from constants import get_repository_directory, get_temp_directory

import os
import shutil
import errno
import stat
import datetime
import tarfile
import re

tar_support = Blueprint('tools', __name__, url_prefix='/tools')


@tar_support.route('/create_tar_file')
@login_required
def create_tar_file():
    select_server_form = SelectServerForm(request.form)
    create_tar_form = CreateTarForm(request.form)
    return render_template('tools/create_tar_file.html',
                           select_server_form = select_server_form,
                           form=create_tar_form)


@tar_support.route('/api/create_tar_job')
@login_required
def api_create_tar_job():
    db_session = DBSession()

    form = CreateTarForm(request.form)

    server_id = request.args.get('server')
    server_directory = request.args.get('server_directory')
    source_tars = request.args.getlist('source_tars[]')
    contents = request.args.getlist('tar_contents[]')
    additional_packages = request.args.getlist('additional_packages[]')
    new_tar_name = request.args.get('new_tar_name').replace('.tar', '')

    create_tar_job = CreateTarJob(
        server_id = server_id,
        server_directory = server_directory,
        source_tars = (',').join(source_tars),
        contents = (',').join(contents),
        additional_packages = (',').join(additional_packages),
        new_tar_name = new_tar_name,
        created_by = current_user.username,
        status = 'Job Submitted.')

    db_session.add(create_tar_job)
    db_session.commit()

    job_id = create_tar_job.id

    return jsonify({'status': 'OK', 'job_id': job_id})

@tar_support.route('/api/get_progress')
@login_required
def get_progress():
    db_session = DBSession()
    job_id = request.args.get('job_id')

    tar_job = db_session.query(CreateTarJob).filter(CreateTarJob.id == job_id).first()
    if tar_job is None:
        logger.error('Unable to retrieve Create Tar Job: %s' % job_id)
        return jsonify(status='Unable to retrieve job')

    return jsonify(status='OK',progress= tar_job.status)


@tar_support.route('/api/get_tar_contents')
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

@tar_support.route('/api/get_full_software_tar_files_from_csm_repository/')
@login_required
def get_full_software_tar_files_from_csm_repository():
    rows = []
    file_list = get_file_list(get_repository_directory())

    for filename in file_list:
        if '-iosxr-' in filename and filename.endswith('.tar'):
            statinfo = os.stat(get_repository_directory() + filename)
            row = {}
            row['image_name'] = filename
            row['image_size'] = '{} bytes'.format(statinfo.st_size)
            rows.append(row)

    return jsonify(**{'data': rows})


@tar_support.route('/api/get_sp_files_from_csm_repository/')
@login_required
def get_sp_files_from_csm_repository():
    rows = []
    file_list = get_file_list(get_repository_directory())

    for filename in file_list:
        if '.pie' in filename or '.smu' in filename:
            statinfo = os.stat(get_repository_directory() + filename)
            row = {}
            row['image_name'] = filename
            row['image_size'] = '{} bytes'.format(statinfo.st_size)
            rows.append(row)

    return jsonify(**{'data': rows})


class CreateTarForm(Form):
    new_tar_name = StringField('New Tar File Name', [required(), Length(max=30)])
