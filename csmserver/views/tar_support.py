from flask import Blueprint
from flask import jsonify, render_template, request
from flask.ext.login import login_required

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
                           form = create_tar_form)

@tar_support.route('/api/create_tar_file')
@login_required
def api_create_tar_job():
    db_session = DBSession()
    server_id = request.args.get('server')
    server_directory = request.args.get('server_directory')
    source_tars = request.args.getlist('source_tars[]')
    contents = request.args.get('tar_contents')
    sps = request.args.getlist('sps[]')
    new_tar_name = request.args.get('new_tar_name').strip('.tar')

    create_tar_job = CreateTarJob()
    create_tar_job.server_id = server_id
    create_tar_job.server_directory = server_directory
    create_tar_job.source_tars = source_tars
    create_tar_job.contents = contents
    create_tar_job.sps = sps
    create_tar_job.new_tar_name = new_tar_name

def api_create_tar_file():
    db_session = DBSession()
    server_id = request.args.get('server')
    server_directory = request.args.get('server_directory')
    source_tars = request.args.getlist('source_tars[]')
    contents = request.args.get('tar_contents')
    sps = request.args.getlist('sps[]')
    new_tar_name = request.args.get('new_tar_name').strip('.tar')

    date_string = datetime.datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")

    repo_dir = get_repository_directory()
    temp_path = get_temp_directory() + str(date_string)
    new_tar_path = os.path.join(temp_path, str(date_string))

    try:
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
            os.makedirs(new_tar_path, 7777)

        # Untar source tars into the temp/timestamp directory
        if source_tars:
            for source in source_tars:
                with tarfile.open(os.path.join(repo_dir, source)) as tar:
                    tar.extractall(temp_path)

        # Copy the selected contents from the temp/timestamp directory
        # to the new tar directory
        if contents:
            for f in contents.strip().split('\n'):
                _, filename = os.path.split(f)
                shutil.copy2(os.path.join(temp_path, filename), new_tar_path)

        # Copy the selected sp files from the repository to the new tar directory
        for sp in sps:
            shutil.copy2(os.path.join(repo_dir, sp), new_tar_path)

        tarname = os.path.join(temp_path, new_tar_name)
        shutil.make_archive(tarname, format='tar', root_dir=new_tar_path)
        make_file_writable(os.path.join(new_tar_path, tarname) + '.tar')

        server = db_session.query(Server).filter(Server.id == server_id).first()
        if server is not None:
            server_impl = get_server_impl(server)
            server_impl.upload_file(tarname + '.tar', new_tar_name + ".tar", sub_directory=server_directory)

        shutil.rmtree(temp_path, onerror=handleRemoveReadonly)
        return jsonify({'status': 'OK'})

    except Exception as e:
        shutil.rmtree(temp_path, onerror=handleRemoveReadonly)
        logger.exception(e)

    return jsonify({'status': e})

def handleRemoveReadonly(func, path, exc):
    excvalue = exc[1]
    if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
        func(path)
    else:
        raise

@tar_support.route('/api/get_tar_contents')
@login_required
def get_tar_contents():
    files = request.args.getlist('files[]')
    files = files[0].strip().split(',')
    rows = []
    repo_path =  get_repository_directory()


    for file in files:
        if file:
            for f in get_tarfile_file_list(repo_path + file):
                row = {}
                row['file'] = repo_path +  file + '/' + f
                row['filename'] = f
                row['source_tar'] = file
                rows.append(row)
    return jsonify( **{'data':rows} )


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

    return jsonify( **{'data':rows} )

@tar_support.route('/api/get_sp_files_from_csm_repository/')
@login_required
def get_sp_files_from_csm_repository():
    rows = []
    file_list = get_file_list(get_repository_directory())

    for filename in file_list:
        if '.pie' in filename:
            statinfo = os.stat(get_repository_directory() + filename)
            row = {}
            row['image_name'] = filename
            row['image_size'] = '{} bytes'.format(statinfo.st_size)
            rows.append(row)

    return jsonify( **{'data':rows} )

class CreateTarForm(Form):
    new_tar_name = StringField('New File Name', [required(), Length(max=30)])
