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
from flask import jsonify

from api_constants import RESPONSE_ENVELOPE

from api_utils import validate_url_parameters
from api_utils import failed_response

from api_constants import HTTP_NOT_FOUND

from smu_info_loader import SMUInfoLoader

from smu_utils import get_optimized_list

from utils import is_empty

import datetime


def api_get_cco_catalog():
    """
    http://localhost:5000/api/v1/cco/catalog
    """
    return jsonify(**{RESPONSE_ENVELOPE: SMUInfoLoader.get_catalog()})


def api_get_cco_software(request):
    """
    http://localhost:5000/api/v1/cco/software?platform=asr9k_px&release=5.3.3
    """
    validate_url_parameters(request, ['platform', 'release', 'date'])

    platform = request.args.get('platform')
    release = request.args.get('release')
    date = request.args.get('date')

    if date:
        date = datetime.datetime.strptime(date, "%m-%d-%Y")
    else:
        date = datetime.datetime.strptime('01-01-2000', "%m-%d-%Y")

    optimal = request.args.get('optimal')

    rows = []
    smu_loader = SMUInfoLoader(platform, release)

    if smu_loader.is_valid:
        if optimal and optimal == 'false':
            smu_list = smu_loader.get_smu_list()
            sp_list = smu_loader.get_sp_list()
        else:
            smu_list = smu_loader.get_optimal_smu_list()
            sp_list = smu_loader.get_optimal_sp_list()

        for smu_info in smu_list:
            if datetime.datetime.strptime(smu_info.posted_date.split()[0], "%m/%d/%Y") >= date:
                rows.append(get_smu_info(smu_info))

        for sp_info in sp_list:
            if datetime.datetime.strptime(sp_info.posted_date.split()[0], "%m/%d/%Y") >= date:
                rows.append(get_smu_info(sp_info))

    if rows:
        return jsonify(**{RESPONSE_ENVELOPE: {'software_list': rows}})

    return failed_response(('Unable to get software information for platform {} ' +
                            'and release {}').format(platform, release))


def api_get_cco_software_entry(request, name_or_id):
    """
    http://localhost:5000/api/v1/cco/software/AA09694?platform=asr9k_px&release=5.3.3
    name_or_id can be the PIMS ID (e.g., AA09694) or the software name (asr9k-p-4.2.3.CSCut30136)
    """
    validate_url_parameters(request, ['platform', 'release'])

    platform = request.args.get('platform')
    release = request.args.get('release')

    smu_loader = SMUInfoLoader(platform, release)
    if smu_loader.is_valid:
        smu_info = smu_loader.get_smu_info(name_or_id)
        if smu_info:
            return jsonify(**{RESPONSE_ENVELOPE: get_smu_info(smu_info)})
        else:
            # Now search for the ID instead of name
            smu_info = smu_loader.get_smu_info_by_id(name_or_id)
            if smu_info:
                return jsonify(**{RESPONSE_ENVELOPE: get_smu_info(smu_info)})

    return failed_response('Unable to locate {}'.format(name_or_id), return_code=HTTP_NOT_FOUND)


def get_smu_info(smu_info):
    row = dict()
    row['id'] = smu_info.id
    row['name'] = smu_info.name
    row['status'] = smu_info.status
    row['type'] = smu_info.type
    row['posted_date'] = smu_info.posted_date
    row['ddts'] = smu_info.ddts
    row['description'] = smu_info.description
    row['functional_areas'] = [] if is_empty(smu_info.functional_areas) else smu_info.functional_areas.split(',')
    row['impact'] = smu_info.impact
    row['package_bundles'] = [] if is_empty(smu_info.package_bundles) else smu_info.package_bundles.split(',')
    row['compressed_image_size'] = str(smu_info.compressed_image_size)
    row['uncompressed_image_size'] = str(smu_info.uncompressed_image_size)
    row['prerequisites'] = [] if is_empty(smu_info.prerequisites) else smu_info.prerequisites.split(',')
    row['supersedes'] = [] if is_empty(smu_info.supersedes) else smu_info.supersedes.split(',')
    row['superseded_by'] = [] if is_empty(smu_info.superseded_by) else smu_info.superseded_by.split(',')
    row['composite_DDTS'] = [] if is_empty(smu_info.composite_DDTS) else smu_info.composite_DDTS.split(',')

    return row


def api_get_optimized_software(request):
    """
    http://localhost:5000/api/v1/cco/get_optimized_list?software_packages=
        ncs5500-os-support-4.0.0.6-r613.CSCve17920.x86_64.rpm,ncs5500-dpa-3.0.0.22-r613.CSCve29118.x86_64.rpm
    """
    validate_url_parameters(request, ['software_packages'])

    rows = []
    result_list = get_optimized_list(request.args.get('software_packages').split(','))

    for result in result_list:
        if result['is'] not in ['Superseded']:
            rows.append(result)

    return jsonify(**{RESPONSE_ENVELOPE: {'software_list': rows}})
