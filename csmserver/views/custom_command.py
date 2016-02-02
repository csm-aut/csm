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
from flask import jsonify, render_template, request, redirect, url_for, abort
from flask.ext.login import login_required, current_user

from database import DBSession

from models import CustomCommandProfile

from wtforms import Form
from wtforms import StringField
from wtforms import TextAreaField
from wtforms.validators import Length, required


custom_command = Blueprint('custom_command', __name__, url_prefix='/custom_command_profiles')


@custom_command.route('/')
@login_required
def home():
    custom_command_profile_form = CustomCommandProfileForm(request.form)
    return render_template('custom_command/custom_command_profile.html',
                           form=custom_command_profile_form)

@custom_command.route('/api/get_command_profiles')
@login_required
def api_get_command_profiles():
    custom_profiles = DBSession().query(CustomCommandProfile).filter().all()

    rows = []
    for profile in custom_profiles:
        row = {'id'          : profile.id,
               'profile_name': profile.profile_name,
               'command_list': profile.command_list,
               'created_by'  : profile.created_by}

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

        command_profile = CustomCommandProfile(
            profile_name=form.profile_name.data,
            command_list=','.join([l for l in form.command_list.data.splitlines() if l]),
            created_by=current_user.username
        )

        db_session.add(command_profile)
        db_session.commit()

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

        command_profile.profile_name = form.profile_name.data
        command_profile.command_list = ','.join([l for l in form.command_list.data.splitlines() if l]),

        db_session.commit()

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

    command_profile = get_command_profile(db_session, profile_name)
    if command_profile is None:
        abort(404)

    db_session.delete(command_profile)
    db_session.commit()

    return jsonify({'status': 'OK'})


def get_command_profile(db_session, profile_name):
    return db_session.query(CustomCommandProfile).filter(CustomCommandProfile.profile_name == profile_name).first()


class CustomCommandProfileForm(Form):
    profile_name = StringField('Profile Name', [required(), Length(max=30)])
    command_list = TextAreaField('Commands')