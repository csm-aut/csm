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
# ==============================================================================
from smu_info_loader import SMUInfoLoader
from flask import jsonify

from api_utils import ENVELOPE
from api_utils import STATUS
from api_utils import STATUS_MESSAGE
from api_utils import APIStatus

import datetime


def api_get_cco_catalog():
    """
    http://localhost:5000/api/v1/cco/catalog
    """
    return jsonify(**{ENVELOPE: SMUInfoLoader.get_catalog()})


def api_get_cco_software(request):
    """
    http://localhost:5000/api/v1/cco/software?platform=asr9k_px&release=5.3.3
    """
    platform = request.args.get('platform')
    release = request.args.get('release')
    date = request.args.get('date')

    try:
        if date:
            date = datetime.datetime.strptime(date, "%m-%d-%Y")
        else:
            date = datetime.datetime.strptime('01-01-2000', "%m-%d-%Y")

        optimal = request.args.get('optimal')

        rows = []
        smu_loader = SMUInfoLoader(platform, release)
        if smu_loader is not None and smu_loader.is_valid:
            smu_list = smu_loader.get_optimal_smu_list()
            if optimal and optimal == 'no':
                smu_list = smu_loader.get_smu_list()

            for smu_info in smu_list:
                if datetime.datetime.strptime(smu_info.posted_date.split()[0], "%m/%d/%Y") >= date:
                    rows.append(get_smu_info(smu_info))

        if rows:
            return jsonify(**{ENVELOPE: {'software_list': rows}})

        return jsonify(**{ENVELOPE: {STATUS: APIStatus.FAILED,
                                     STATUS_MESSAGE: ('Unable to get software information for platform {} ' +
                                                      'and release {}').format(platform, release)}}), 400
    except Exception as e:
        return jsonify(**{ENVELOPE: {STATUS: APIStatus.FAILED,
                                     STATUS_MESSAGE: e.message}}), 400


def api_get_cco_software_entry(request, name_or_id):
    """
    http://localhost:5000/api/v1/cco/software/AA09694?platform=asr9k_px&release=5.3.3
    name_or_id can be the PIMS ID (e.g., AA09694) or the software name (asr9k-p-4.2.3.CSCut30136)
    """
    platform = request.args.get('platform')
    release = request.args.get('release')

    smu_loader = SMUInfoLoader(platform, release)
    if smu_loader is not None and smu_loader.is_valid:
        smu_info = smu_loader.get_smu_info(name_or_id)
        if smu_info:
            return jsonify(**{ENVELOPE: get_smu_info(smu_info)})
        else:
            # Now search for the ID instead of name
            smu_info = smu_loader.get_smu_info_by_id(name_or_id)
            if smu_info:
                return jsonify(**{ENVELOPE: get_smu_info(smu_info)})

    return jsonify(**{ENVELOPE: {STATUS: APIStatus.FAILED, STATUS_MESSAGE: 'Unable to locate %s' % name_or_id}}), 404


def get_smu_info(smu_info):
    row = {}
    row['id'] = smu_info.id
    row['name'] = smu_info.name
    row['status'] = smu_info.status
    row['type'] = smu_info.type
    row['posted_date'] = smu_info.posted_date
    row['ddts'] = smu_info.ddts
    row['description'] = smu_info.description
    row['functional_areas'] = smu_info.functional_areas
    row['impact'] = smu_info.impact
    row['package_bundles'] = smu_info.package_bundles
    row['compressed_image_size'] = str(smu_info.compressed_image_size)
    row['uncompressed_image_size'] = str(smu_info.uncompressed_image_size)
    row['prerequisites'] = smu_info.prerequisites
    row['supersedes'] = smu_info.supersedes
    row['superseded_by'] = smu_info.superseded_by
    row['composite_DDTS'] = smu_info.composite_DDTS

    return row
