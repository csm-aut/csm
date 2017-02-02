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
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import jsonify

from flask.ext.login import login_required
from flask.ext.login import current_user
from flask.ext.login import login_user
from flask.ext.login import logout_user

from wtforms import Form
from wtforms import StringField
from wtforms import SelectField
from wtforms import PasswordField
from wtforms import HiddenField
from wtforms.validators import required

from database import DBSession

from common import can_create_user
from common import get_user_list
from common import get_user
from common import fill_user_privileges

from models import User
from models import logger
from models import Preferences
from models import SystemOption
from models import UserPrivilege
from models import CSMMessage

from wtforms.validators import Required

from utils import get_base_url
from utils import get_return_url

from smu_info_loader import SMUInfoLoader

import datetime

authenticate = Blueprint('authenticate', __name__, url_prefix='/authenticate')


@authenticate.route('/login/', methods=['GET', 'POST'])
def login():

    form = LoginForm(request.form)
    error_message = None

    if request.method == 'POST' and form.validate():
        username = form.username.data.strip()
        password = form.password.data.strip()

        db_session = DBSession()

        user, authenticated = \
            User.authenticate(db_session.query, username, password)

        if authenticated:
            login_user(user)

            # record the base URL
            try:
                system_option = SystemOption.get(db_session)
                system_option.base_url = get_base_url(request.url)
                db_session.commit()
            except:
                logger.exception('login() hit exception')

            # Certain admin features (Admin Console/Create or Edit User require
            # re-authentication. The return_url indicates which admin feature the
            # user wants to access.
            return_url = get_return_url(request)
            if return_url is None:
                return redirect(request.args.get("next") or url_for('home'))
            else:
                return redirect(url_for(return_url))
        else:
            error_message = 'Your user name or password is incorrect.  \
                             Re-enter them again or contact your system administrator.'

    # Fill the username if the user is still logged in.
    username = get_username(current_user)
    if username is not None:
        form.username.data = username

    return render_template('user/login.html', form=form, error_message=error_message, username=username)


def get_username(current_user):
    """
    Return the current username.  If the user already logged out, return None
    """
    try:
        return current_user.username
    except:
        return None


@authenticate.route('/logout/')
def logout():
    logout_user()
    return redirect(url_for('authenticate.login'))


@authenticate.route('/users/create', methods=['GET','POST'])
@login_required
def user_create():
    if not can_create_user(current_user):
        abort(401)

    form = UserForm(request.form)
    # Need to add the Required flag back as it is globally removed during user_edit()
    add_validator(form.password, Required)

    fill_user_privileges(form.privilege.choices)

    if request.method == 'POST' and form.validate():
        db_session = DBSession()
        user = get_user(db_session, form.username.data)

        if user is not None:
            return render_template('user/edit.html', form=form, duplicate_error=True)

        user = User(
            username=form.username.data,
            password=form.password.data,
            privilege=form.privilege.data,
            fullname=form.fullname.data,
            email=form.email.data)

        user.preferences.append(Preferences())
        db_session.add(user)
        db_session.commit()

        return redirect(url_for('home'))
    else:
        # Default to Active
        form.active.data = True
        return render_template('user/edit.html', form=form)


@authenticate.route('/users/<username>/edit', methods=['GET','POST'])
@login_required
def user_edit(username):
    db_session = DBSession()

    user = get_user(db_session, username)
    if user is None:
        abort(404)

    form = UserForm(request.form)
    fill_user_privileges(form.privilege.choices)

    if request.method == 'POST' and form.validate():

        if len(form.password.data) > 0:
            user.password = form.password.data

        user.privilege = form.privilege.data
        user.fullname = form.fullname.data
        user.email = form.email.data
        user.active = form.active.data
        db_session.commit()

        return redirect(url_for('home'))
    else:
        form.username.data = user.username
        # Remove the Required flag so validation won't fail.  In edit mode, it is okay
        # not to provide the password.  In this case, the password on file is used.
        remove_validator(form.password, Required)

        form.privilege.data = user.privilege
        form.fullname.data = user.fullname
        form.email.data = user.email
        form.active.data = user.active

    return render_template('user/edit.html', form=form)


@authenticate.route('/users/edit', methods=['GET','POST'])
@login_required
def current_user_edit():
    return user_edit(current_user.username)


@authenticate.route('/users/')
@login_required
def user_list():
    db_session = DBSession()

    users = get_user_list(db_session)
    if users is None:
        abort(404)

    if current_user.privilege == UserPrivilege.ADMIN:
        return render_template('user/index.html', users=users, system_option=SystemOption.get(db_session))

    return render_template('user/not_authorized.html', user=current_user)


@authenticate.route('/users/<username>/delete/', methods=['DELETE'])
@login_required
def user_delete(username):
    db_session = DBSession()

    user = get_user(db_session, username)
    if user is None:
        abort(404)

    db_session.delete(user)
    db_session.commit()

    return jsonify({'status': 'OK'})


def add_validator(field, validator_class):
    validators = field.validators
    for v in validators:
        if isinstance(v, validator_class):
            return

    validators.append(validator_class())


def remove_validator(field, validator_class):
    validators = field.validators
    for v in validators:
        if isinstance(v, validator_class):
            validators.remove(v)


@authenticate.route('/api/acknowledge_csm_message', methods=['POST'])
def api_acknowledge_csm_message():
    username = request.form['username']
    password = request.form['password']

    db_session = DBSession()

    user, authenticated = \
        User.authenticate(db_session.query, username, password)

    if authenticated:
        if len(user.csm_message) == 0:
            user.csm_message.append(CSMMessage(acknowledgment_date=datetime.date.today() ))
        else:
            user.csm_message[0].acknowledgment_date=datetime.date.today()

        db_session.commit()

    return jsonify({'status': 'OK'})


@authenticate.route('/api/get_csm_message', methods=['POST'])
def api_get_csm_message():
    rows = []

    username = request.form['username']
    password = request.form['password']

    db_session = DBSession()

    user, authenticated = \
        User.authenticate(db_session.query, username, password)

    if authenticated:
        # if user.privilege == UserPrivilege.ADMIN:
        csm_messages = SMUInfoLoader.get_cco_csm_messages()
        if len(csm_messages) > 0:
            acknowledgment_date = datetime.datetime(2000, 1, 1)
            if len(user.csm_message) > 0:
                acknowledgment_date = user.csm_message[0].acknowledgment_date

            # csm_messages returns a dictionary keyed by a token (e.g. @12/01/01@Admin,Operator) and message
            readers = [ UserPrivilege.ADMIN, UserPrivilege.NETWORK_ADMIN, UserPrivilege.OPERATOR, UserPrivilege.VIEWER]
            for csm_message in csm_messages:
                tokens = csm_message['token'].split('@')
                date = tokens[0]
                if len(tokens) == 2:
                    readers = tokens[1].split(',')

                if user.privilege in readers:
                    message = csm_message['message']
                    try:
                        delta = datetime.datetime.strptime(date, "%Y/%m/%d") - acknowledgment_date
                        if delta.days > 0:
                            rows.append({'date': date, 'message': message.replace("\n", "<br>")})
                    except:
                        logger.exception('api_get_csm_message() hit exception')

    return jsonify(**{'data': rows})


class LoginForm(Form):
    """
    Render HTML input for user login form.
    Authentication (i.e. password verification) happens in the view function.
    """
    username = StringField('Username', [required()])
    password = PasswordField('Password', [required()])


class UserForm(Form):
    """
    Render HTML input for user registration form.
    Authentication (i.e. password verification) happens in the view function.
    """
    username = StringField('Username', [required()])
    password = PasswordField('Password', [required()])
    privilege = SelectField('Privilege', [required()], coerce=str, choices=[('', '')])
    active = HiddenField("Active")
    fullname = StringField('Full Name', [required()])
    email = StringField('Email Address', [required()])

