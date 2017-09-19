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
from flask import render_template, jsonify, abort, send_file, flash
from flask.ext.login import login_required, current_user
from flask import request, redirect, url_for

from wtforms import Form
from wtforms import StringField
from wtforms import SelectMultipleField
from wtforms.validators import Length, required

from constants import InstallAction

from common import can_delete
from common import can_install
from common import get_return_url
from common import get_mop_list
from common import get_mop_specs_with_mop_name
from common import get_existing_software_platform
from common import get_region_by_id
from common import translate_software_platform_to_platform_os

from csmpe import get_available_plugins

from database import DBSession

from models import logger
from models import Mop
from models import SystemOption
from models import ConnectionParam


mop = Blueprint('mop', __name__, url_prefix='/mop')


@mop.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if not can_install(current_user):
        abort(401)

    return render_template('mop/index.html')


@mop.route('/get_available_plugins_and_required_data', methods=['POST'])
@login_required
def get_available_plugins_and_required_data():
    if not can_install(current_user):
        abort(401)
    phases = request.form.getlist('phases[]')
    software_platforms = request.form.getlist('platforms[]')

    return jsonify(plugin_specs=get_available_plugin_specs(software_platforms, phases))


def get_all_available_plugins(platform=None, phases=None, os_type=None):
    if phases:
        return get_available_plugins(platform=platform, phase=phases, os=os_type)
    # if phases is not specified, get available plugins for all valid mop phases
    plugins = dict()
    for phase in get_phases():
        plugins.update(get_available_plugins(platform=platform, phase=phase, os=os_type))
    return plugins


def get_available_plugin_specs(software_platforms, phases):
    if not software_platforms:
        plugin_specs = get_all_available_plugins(phases=phases)
        plugins = plugin_specs.keys()
    else:
        platform, os_type = translate_software_platform_to_platform_os(software_platforms[0])
        plugin_specs = get_all_available_plugins(platform=platform, phases=phases, os_type=os_type)
        plugins = set(plugin_specs.keys())

        for i in range(1, len(software_platforms)):
            platform, os_type = translate_software_platform_to_platform_os(software_platforms[i])
            plugin_set = get_all_available_plugins(platform=platform, phases=phases, os_type=os_type).keys()
            if plugins:
                plugins.intersection_update(plugin_set)
            else:
                break

    available_plugin_specs = {}
    for plugin in plugins:
        available_plugin_specs[plugin] = plugin_specs[plugin]

    return available_plugin_specs


@mop.route('/api/get_mops', defaults={'platform': None, 'phase': None})
@mop.route('/api/get_mops/platform/<string:platform>', defaults={'phase': None})
@mop.route('/api/get_mops/phase/<string:phase>', defaults={'platform': None})
@mop.route('/api/get_mops/platform/<string:platform>/phase/<string:phase>')
@login_required
def api_get_mops(platform, phase):
    if not can_install(current_user):
        abort(401)
    db_session = DBSession()

    mops = get_mop_list(db_session, platform=platform, phase=phase)

    return jsonify(**{'data': mops})


@mop.route('/api/delete/<mop_name>', methods=['DELETE'])
@login_required
def api_delete_mop(mop_name):
    if not can_delete(current_user):
        abort(401)
    db_session = DBSession()

    try:
        db_session.query(Mop).filter(Mop.name == mop_name).delete(synchronize_session=False)
        db_session.commit()
        db_session.close()
        return jsonify({'status': 'OK'})
    except Exception as e:
        logger.exception('api_delete_mop hit exception.')
        return jsonify({'status': e.message})


@mop.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not can_install(current_user):
        abort(401)
    db_session = DBSession()
    mop_form = MopForm(request.form)

    return_url = get_return_url(request, 'mop.home')

    if request.method == 'GET':
        init_mop_form(mop_form, db_session)
        return render_template('mop/edit.html', system_option=SystemOption.get(db_session), current_user=current_user,
                               form=mop_form, mop_specs=[],
                               duplicate_error=False)

    if request.method == 'POST':
        mop = db_session.query(Mop).filter(Mop.name == mop_form.mop_name.data).first()

        if mop is not None:
            return render_template('mop/edit.html',
                                   form=mop_form,
                                   mop_specs=[],
                                   system_option=SystemOption.get(db_session),
                                   duplicate_error=True)
        return create_new_mop(db_session, request.get_json(), return_url)


@mop.route('/<mop_name>/edit', methods=['GET', 'POST'])
@login_required
def edit(mop_name):
    if not can_install(current_user):
        abort(401)

    db_session = DBSession()

    mops_query = db_session.query(Mop).filter(Mop.name == mop_name)

    if not mops_query.all():
        abort(404)

    phases = [mop_entry.phase for mop_entry in mops_query]
    platforms = [mop_entry.software_platform for mop_entry in mops_query]

    mop_form = MopForm(request.form)

    return_url = get_return_url(request, 'mop.home')

    if request.method == 'GET':
        init_mop_form(mop_form, db_session)
        mop_form.mop_name.data = mop_name
        mop_form.phase.data = phases
        mop_form.platform.data = platforms

        return render_template('mop/edit.html', system_option=SystemOption.get(db_session), current_user=current_user,
                               form=mop_form, mop_specs=get_mop_specs_with_mop_name(db_session, mop_name),
                               duplicate_error=False)

    if request.method == 'POST':
        mops_query.delete()
        db_session.commit()
        return create_new_mop(db_session, request.get_json(), return_url)


@mop.route('/api/get_mop_specs/<mop_name>', methods=['POST'])
@login_required
def api_get_mop_specs(mop_name):
    db_session = DBSession()
    phases = request.form.getlist('phases[]')
    software_platforms = request.form.getlist('platforms[]')

    return jsonify(plugin_specs=get_available_plugin_specs(software_platforms, phases),
                   mop_specs=get_mop_specs_with_mop_name(db_session, mop_name))


def create_new_mop(db_session, mop_details, return_url):

    try:
        name = mop_details["name"]
        phases = mop_details["phases"]
        platforms = mop_details["platforms"]
        specs = mop_details["specs"]

        mops = []
        for idx in range(len(specs)):
            for phase in phases:
                for platform in platforms:
                    mops.append(Mop(name=name,
                                    plugin_name=specs[idx]["plugin"],
                                    plugin_idx=idx,
                                    phase=phase,
                                    software_platform=platform,
                                    created_by=current_user.username,
                                    plugin_data=specs[idx]["data"]))
    except KeyError as e:
        logger.exception('create new mop hit exception: '.format(e))
        return jsonify(redirect_url=url_for(return_url))

    db_session.add_all(mops)
    db_session.commit()
    db_session.close()
    return jsonify(redirect_url=url_for(return_url))


def init_mop_form(mop_form, db_session):
    del mop_form.phase.choices[:]
    mop_form.phase.choices = get_phase_choices()
    mop_form.platform.choices = get_software_platform_choices(db_session)


def get_phases():
    return [InstallAction.PRE_CHECK, InstallAction.POST_CHECK]


def get_phase_choices():
    phases = get_phases()
    phases_choices = [(phase, phase) for phase in phases]
    phases_choices.append(("ALL", "ALL"))
    return phases_choices


def get_software_platform_choices(db_session):
    #platforms = [(value, value) for key, value in vars(PlatformFamily).iteritems() if not key.startswith('_')]
    platforms = [(platform[0], platform[0]) for platform in get_existing_software_platform(db_session)]
    platforms.append(("ALL", "ALL"))
    return platforms


def substitute_env_vars(db_session, host, expression):
    if expression is None:
        return None
    expression = expression.replace("@hostname", host.hostname)
    expression = expression.replace("@host_chassis", host.platform)
    expression = expression.replace("@host_platform", host.software_platform)
    expression = expression.replace("@host_software_version", host.software_version)

    if "@host_ip" in expression or "@host_port_number" in expression or "@host_connection_type" in expression:
        connection_param = db_session.query(ConnectionParam).filter(ConnectionParam.host_id == host.id).first()
        expression = expression.replace("@host_ip", connection_param.host_or_ip)
        expression = expression.replace("@host_port_number", connection_param.port_number)
        expression = expression.replace("@host_connection_type", connection_param.connection_type)

    if "@host_region" in expression:
        expression = expression.replace("@host_region", get_region_by_id(db_session, host.region_id)[0])
    return expression


class MopForm(Form):
    mop_name = StringField('MOP Name', [required(), Length(max=30)])
    phase = SelectMultipleField('Phase', coerce=str, choices=[('', '')])
    platform = SelectMultipleField('Platform', coerce=str, choices=[('', '')])
