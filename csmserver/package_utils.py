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
from constants import PlatformFamily

# The key is part of the internal name, the value is part of the external name (without version info)

CRS_PACKAGES = {
    'hfr-asr9000v-nV-px': 'hfr-asr9000v-nV-px.pie',
    'hfr-diags-px': 'hfr-diags-px.pie',
    'hfr-doc-px': 'hfr-doc-px.pie',
    'hfr-fit-px': 'hfr-fit-px.pie',
    'hfr-fpd-px': 'hfr-fpd-px.pie',
    'hfr-infra-test-px': 'hfr-infra-test-px.pie',
    'hfr-k9sec-px': 'hfr-k9sec-px.pie',
    'hfr-li-px': 'hfr-li-px.pie',
    'hfr-mcast-px': 'hfr-mcast-px.pie',
    'hfr-mgbl-px': 'hfr-mgbl-px.pie',
    'hfr-mini-px': 'hfr-mini-px.pie',
    'hfr-mpls-px': 'hfr-mpls-px.pie',
    'hfr-pagent-px': 'hfr-pagent-px.pie',
    'hfr-services-px': 'hfr-services-px.pie',
    'hfr-upgrade-px': 'hfr-upgrade-px.pie',
    'hfr-video-px': 'hfr-video-px.pie'
}

       
ASR9K_PACKAGES = {
    'asr9k-9000v-nV-px': 'asr9k-asr9000v-nV-px.pie',
    'asr9k-asr901-nV-px': 'asr9k-asr901-nV-px.pie',
    'asr9k-asr903-nV-px': 'asr9k-asr903-nV-px.pie',
    'asr9k-bng-px': 'asr9k-bng-px.pie',
    'asr9k-doc-px': 'asr9k-doc-px.pie',
    'asr9k-fpd-px': 'asr9k-fpd-px.pie',
    'asr9k-infra-test-px': 'asr9k-infra-test-px.pie',
    'asr9k-k9sec-px': 'asr9k-k9sec-px.pie',
    'asr9k-li-px': 'asr9k-li-px.pie',
    'asr9k-mcast-px': 'asr9k-mcast-px.pie',
    'asr9k-mgbl-px': 'asr9k-mgbl-px.pie',
    'asr9k-mini-px': 'asr9k-mini-px.pie',
    'asr9k-mpls-px': 'asr9k-mpls-px.pie',
    'asr9k-optic-px': 'asr9k-optic-px.pie',
    'asr9k-services-infra': 'asr9k-services-infra-px.pie',
    'asr9k-services-px': 'asr9k-services-px.pie',
    'asr9k-video-px': 'asr9k-video-px.pie',
}

NCS6K_PACKAGES = {
    'ncs6k-doc': 'ncs6k-doc.pkg',
    'ncs6k-li': 'ncs6k-li.pkg',
    'ncs6k-mcast': 'ncs6k-mcast.pkg',
    'ncs6k-mgbl': 'ncs6k-mgbl.pkg',
    'ncs6k-mpls': 'ncs6k-mpls.pkg',
    'ncs6k-k9sec': 'ncs6k-k9sec.pkg',
    'ncs6k-xr': 'ncs6k-mini-x.iso',
}


def get_target_software_package_list(family, host_packages, target_version, match_internal_name=False):
    """
    If match_internal_name is true, it matches the host_packages instead of the physical name
    on the server repository.
    """
    target_list = []
    platform_package_list = {}
    
    if family == PlatformFamily.ASR9K:
        platform_package_list = ASR9K_PACKAGES
    elif family == PlatformFamily.CRS:
        platform_package_list = CRS_PACKAGES
    elif family == PlatformFamily.NCS6K:
        platform_package_list = NCS6K_PACKAGES
        
    for k, v in platform_package_list.items():
        for package in host_packages:
            if k in package:
                if match_internal_name:
                    target_list.append("{}-{}".format(k, target_version))
                else:
                    target_list.append("{}-{}".format(v, target_version))
    
    return target_list
