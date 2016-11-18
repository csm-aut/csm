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
from flask import jsonify, render_template, request, redirect, url_for, abort, send_file, flash
from flask.ext.login import login_required, current_user

from database import DBSession

from models import CustomCommandProfile
from constants import get_temp_directory

from wtforms import Form
from wtforms import StringField
from wtforms import TextAreaField
from wtforms.validators import Length, required

from utils import create_temp_user_directory
from utils import create_directory
from utils import make_file_writable

from common import create_or_update_custom_command_profile
from common import delete_custom_command_profile as delete_ccp
from common import get_custom_command_profile

import os
import json

custom_command = Blueprint('custom_command', __name__, url_prefix='/custom_command_profiles')


@custom_command.route('/', methods=['GET', 'POST'])
@login_required
def home():
    msg = ''
    # Custom Command Profile import
    if request.method == 'POST':
        file = request.files['file']
        if file:
            if not allowed_file(file.filename):
                msg = "Incorrect file format -- " + file.filename + " must be .json"
            else:
                file_path = os.path.join(get_temp_directory(), "custom_command_profiles.json")
                file.save(file_path)
                failed = ""

                with open(file_path, 'r') as f:
                    try:
                        s = json.load(f)
                    except:
                        msg = "Incorrect file format -- " + file.filename + " must be a valid JSON file."
                        flash(msg, 'import_feedback')
                        return redirect(url_for(".home"))

                    if "CSM Server:Custom Command Profile" not in s.keys():
                        msg = file.filename + " is not in the correct Custom Command Profile format."
                    else:
                        db_session = DBSession
                        custom_profiles = [p for (p,) in DBSession().query(CustomCommandProfile.profile_name).all()]
                        d = s["CSM Server:Custom Command Profile"]

                        for profile_name in d.keys():
                            name = ''
                            if profile_name in custom_profiles:
                                name = profile_name
                                # Will keep appending ' - copy' until it hits a unique name
                                while name in custom_profiles:
                                    name += " - copy"
                                msg += profile_name + ' -> ' + name + '\n'
                                custom_profiles.append(name)

                            if len(name) < 100 and len(profile_name) < 100:
                                try:
                                    profile = CustomCommandProfile(
                                        profile_name=name if name else profile_name,
                                        command_list=d[profile_name],
                                        created_by=current_user.username
                                    )
                                    db_session.add(profile)
                                    db_session.commit()
                                except:
                                    failed += profile_name + '\n'
                            else:
                                failed += profile_name + ' (name too long)\n'

                        if msg:
                            msg = "The following profiles already exist and will try to be imported under modified names:\n\n" + \
                                msg + '\n'
                            if failed:
                                msg += 'The following profiles failed to import:\n\n' + failed
                        elif failed:
                            msg = 'The following profiles failed to import:\n\n' + failed
                        else:
                            msg = "Custom Command Profile import was successful!"

                # delete file
                os.remove(file_path)

            flash(msg, 'import_feedback')
            return redirect(url_for(".home"))

    custom_command_profile_form = CustomCommandProfileForm(request.form)
    return render_template('custom_command/custom_command_profile.html',
                           form=custom_command_profile_form)


@custom_command.route('/api/get_command_profiles')
@login_required
def api_get_command_profiles():
    custom_profiles = DBSession().query(CustomCommandProfile).filter().all()

    rows = []
    for profile in custom_profiles:
        row = {'id': profile.id,
               'profile_name': profile.profile_name,
               'command_list': profile.command_list,
               'created_by': profile.created_by}

        rows.append(row)

    return jsonify(**{'data': rows})


@custom_command.route('/command_profile/create', methods=['GET', 'POST'])
@login_required
def command_profile_create():
    db_session = DBSession()

    form = CustomCommandProfileForm(request.form)

    if request.method == 'POST' and form.validate():
        command_profile = get_command_profile(db_session, form.profile_name.data)

        if command_profile is not None:
            return render_template('custom_command/command_profile_edit.html',
                                   form=form, duplicate_error=True)

        #command_profile = CustomCommandProfile(
        #    profile_name=form.profile_name.data,
        #    command_list=','.join([l for l in form.command_list.data.splitlines() if l]),
        #    created_by=current_user.username
        #)

        command_profile = create_or_update_custom_command_profile(
            db_session=db_session,
            profile_name=form.profile_name.data,
            command_list=','.join([l for l in form.command_list.data.splitlines() if l])
        )

        #db_session.add(command_profile)
        #db_session.commit()

        return redirect(url_for('custom_command.home'))
    else:

        return render_template('custom_command/command_profile_edit.html',
                               form=form)


@custom_command.route('/command_profile/<profile_name>/edit', methods=['GET', 'POST'])
@login_required
def command_profile_edit(profile_name):
    db_session = DBSession()

    command_profile = get_command_profile(db_session, profile_name)
    if command_profile is None:
        abort(404)

    form = CustomCommandProfileForm(request.form)

    if request.method == 'POST' and form.validate():
        if profile_name != form.profile_name.data and \
                        get_command_profile(db_session, form.profile_name.data) is not None:
            return render_template('custom_commad/command_profile_edit.html',
                                   form=form, duplicate_error=True)

        #command_profile.profile_name = form.profile_name.data
        #command_profile.command_list = ','.join([l for l in form.command_list.data.splitlines() if l]),

        #db_session.commit()

        command_profile = create_or_update_custom_command_profile(
            db_session=db_session,
            profile_name=form.profile_name.data,
            command_list=','.join([l for l in form.command_list.data.splitlines() if l]),
            custom_command_profile=get_custom_command_profile(db_session, profile_name)
        )

        return redirect(url_for('custom_command.home'))
    else:
        form.profile_name.data = command_profile.profile_name
        if command_profile.command_list is not None:
            form.command_list.data = '\n'.join(command_profile.command_list.split(','))

    return render_template('custom_command/command_profile_edit.html',
                           form=form)


@custom_command.route('/command_profile/<profile_name>/delete', methods=['DELETE'])
@login_required
def delete_custom_command_profile(profile_name):
    db_session = DBSession()

    #command_profile = get_command_profile(db_session, profile_name)
    #if command_profile is None:
    #    abort(404)

    #db_session.delete(command_profile)
    #db_session.commit()

    try:
        delete_ccp(db_session, profile_name)
        return jsonify({'status': 'OK'})
    except:
        abort(404)


def get_command_profile(db_session, profile_name):
    return db_session.query(CustomCommandProfile).filter(CustomCommandProfile.profile_name == profile_name).first()


def get_command_profile_by_id(db_session, profile_id):
    return db_session.query(CustomCommandProfile).filter(CustomCommandProfile.id == profile_id).first()


@custom_command.route('/export_command_profiles', methods=['POST'])
@login_required
def export_command_profiles():
    db_session = DBSession()
    profiles_list = request.args.getlist('profiles_list[]')[0].split(",")
    db_profiles = db_session.query(CustomCommandProfile).all()
    d = {"CSM Server:Custom Command Profile": {}}

    for profile in db_profiles:
        if profile.profile_name in profiles_list:
            d["CSM Server:Custom Command Profile"][profile.profile_name] = profile.command_list

    temp_user_dir = create_temp_user_directory(current_user.username)
    custom_command_export_temp_path = os.path.normpath(os.path.join(temp_user_dir, "custom_command_export"))
    create_directory(custom_command_export_temp_path)
    make_file_writable(custom_command_export_temp_path)

    with open(os.path.join(custom_command_export_temp_path, 'custom_command_profiles.json'), 'w') as command_export_file:
        command_export_file.write(json.dumps(d, indent=2))

    return send_file(os.path.join(custom_command_export_temp_path, 'custom_command_profiles.json'), as_attachment=True)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ['json']


class CustomCommandProfileForm(Form):
    profile_name = StringField('Profile Name', [required(), Length(max=30)])
    command_list = TextAreaField('CLI Commands')