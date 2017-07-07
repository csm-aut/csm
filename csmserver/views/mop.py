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
from wtforms import HiddenField
from wtforms import SelectMultipleField
from wtforms.validators import Length, required

from constants import InstallAction
from constants import PlatformFamily

from common import can_delete
from common import can_install
from common import get_return_url
from common import get_mop_list
from common import get_plugins_execution_order_string_with_mop_name

from csmpe import get_available_plugins

from database import DBSession

from models import logger
from models import Mop
from models import SystemOption


mop = Blueprint('mop', __name__, url_prefix='/mop')


@mop.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if not can_install(current_user):
        abort(401)

    return render_template('mop/index.html')


@mop.route('/get_available_plugin_list', methods=['POST'])
@login_required
def get_available_plugin_list():
    if not can_install(current_user):
        abort(401)
    phases = request.form.getlist('phases[]')
    platforms = request.form.getlist('platforms[]')

    if not platforms:
        plugins = get_all_available_plugins(phases=phases)
    else:
        plugins = set()
        for software_platform in platforms:
            platform, os_type = translate_software_platform_to_platform_os(software_platform)
            if not plugins:
                plugins = get_all_available_plugins(platform=platform, phases=phases, os_type=os_type)
            else:
                plugins = set.intersection(plugins,
                                           get_all_available_plugins(platform=platform, phases=phases, os_type=os_type))

    return jsonify(plugins=sorted(plugins))


def get_all_available_plugins(platform=None, phases=None, os_type=None):
    if phases:
        return set(get_available_plugins(platform=platform, phase=phases, os=os_type))
    # if phases is not specified, get available plugins for all valid mop phases
    plugins = set()
    for phase in get_phases():
        plugins = set.union(set(get_available_plugins(platform=platform, phase=phase, os=os_type)))
    return plugins


def translate_software_platform_to_platform_os(software_platform):
    if software_platform in [PlatformFamily.ASR9K, PlatformFamily.CRS]:
        return software_platform, "XR"
    elif software_platform == PlatformFamily.ASR9K_X64:
        return PlatformFamily.ASR9K, "eXR"
    elif software_platform == PlatformFamily.IOSXRv_X64:
        return "IOS-XRv", "eXR"
    elif software_platform == PlatformFamily.ASR900:
        return PlatformFamily.ASR900, None # IOS or XE
    elif software_platform == PlatformFamily.CRS:
        return PlatformFamily.CRS, "XR"
    elif software_platform in [PlatformFamily.NCS1K, PlatformFamily.NCS4K,
                               PlatformFamily.NCS5K, PlatformFamily.NCS5500, PlatformFamily.NCS6K]:
        return software_platform, "eXR"
    else:
        return software_platform, None


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


@mop.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    if not can_install(current_user):
        abort(401)
    db_session = DBSession()
    mop_form = MopForm(request.form)

    return_url = get_return_url(request, 'mop.home')

    if request.method == 'GET':
        init_mop_form(mop_form)
        return render_template('mop/edit.html', system_option=SystemOption.get(db_session), current_user=current_user,
                               form=mop_form, duplicate_error=False)

    if request.method == 'POST':

        mop = db_session.query(Mop).filter(Mop.name == mop_form.mop_name.data).first()

        if mop is not None:
            return render_template('mop/edit.html',
                                   form=mop_form,
                                   system_option=SystemOption.get(db_session),
                                   duplicate_error=True)

        plugins = mop_form.hidden_plugins.data.split(',')
        phases = mop_form.phase.data
        platforms = mop_form.platform.data
        mops = []
        for idx in range(len(plugins)):
            for phase in phases:
                for platform in platforms:
                    mops.append(Mop(name=mop_form.mop_name.data,
                                    plugin_name=plugins[idx],
                                    plugin_idx=idx,
                                    phase=phase,
                                    software_platform=platform,
                                    created_by=current_user.username,
                                    plugin_data={}))

        db_session.add_all(mops)
        db_session.commit()
        db_session.close()
        return redirect(url_for(return_url))


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
        init_mop_form(mop_form)
        mop_form.mop_name.data = mop_name
        mop_form.phase.data = phases
        mop_form.platform.data = platforms
        mop_form.hidden_plugins.data = get_plugins_execution_order_string_with_mop_name(db_session, mop_name)

        return render_template('mop/edit.html', system_option=SystemOption.get(db_session), current_user=current_user,
                               form=mop_form,
                               duplicate_error=False)

    if request.method == 'POST':
        mops_query.delete()
        db_session.commit()
        plugins = mop_form.hidden_plugins.data.split(',')
        phases = mop_form.phase.data
        platforms = mop_form.platform.data
        mops = []
        for idx in range(len(plugins)):
            for phase in phases:
                for platform in platforms:
                    print plugins[idx]
                    mops.append(Mop(name=mop_form.mop_name.data,
                                    plugin_name=plugins[idx],
                                    plugin_idx=idx,
                                    phase=phase,
                                    software_platform=platform,
                                    created_by=current_user.username,
                                    plugin_data={}))

        db_session.add_all(mops)
        db_session.commit()
        db_session.close()
        return redirect(url_for(return_url))


def init_mop_form(mop_form):
    del mop_form.phase.choices[:]
    mop_form.phase.choices = get_phase_choices()
    mop_form.platform.choices = get_software_platform_choices()
    mop_form.hidden_plugins.data = ''


def get_phases():
    return [InstallAction.PRE_UPGRADE, InstallAction.POST_UPGRADE]


def get_phase_choices():
    phases = get_phases()
    phases_choices = [(phase, phase) for phase in phases]
    phases_choices.append(("ALL", "ALL"))
    return phases_choices


def get_software_platform_choices():
    platforms = [(value, value) for key, value in vars(PlatformFamily).iteritems() if not key.startswith('_')]
    platforms.append(("ALL", "ALL"))
    return platforms


class MopForm(Form):
    mop_name = StringField('MOP Name', [required(), Length(max=30)])
    phase = SelectMultipleField('Phase', coerce=str, choices=[('', '')])
    platform = SelectMultipleField('Platform', coerce=str, choices=[('', '')])
    hidden_plugins = HiddenField('')
