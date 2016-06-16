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

import re

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

# When matching, ASR9K X64 packages will be matched as regex
# The others will be used as literal string
#
# Engineering Names:
# asr9k-mcast-x64-2.0.0.0-r61113I          asr9k-mcast-x64-2.0.0.0-r61113I.x86_64.rpm-6.1.1
#
# Production Images:
# Internal Names:                          External Names:
#
# asr9k-bgp-x64-1.0.0.0-r611               asr9k-bgp-x64-1.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-diags-x64-1.0.0.0-r611             asr9k-diags-x64-1.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-eigrp-x64-1.0.0.0-r611             asr9k-eigrp-x64-1.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-isis-x64-1.1.0.0-r611              asr9k-isis-x64-1.1.0.0-r611.x86_64.rpm-6.1.1
# asr9k-k9sec-x64-2.1.0.0-r611             asr9k-k9sec-x64-2.1.0.0-r611.x86_64.rpm-6.1.1
# asr9k-li-x64-1.1.0.0-r611                asr9k-li-x64-1.1.0.0-r611.x86_64.rpm-6.1.1
# asr9k-m2m-x64-2.0.0.0-r611               asr9k-m2m-x64-2.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-mcast-x64-2.0.0.0-r611             asr9k-mcast-x64-2.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-mgbl-x64-3.0.0.0-r611              asr9k-mgbl-x64-3.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-mpls-te-rsvp-x64-1.1.0.0-r611      asr9k-mpls-te-rsvp-x64-1.1.0.0-r611.x86_64.rpm-6.1.1
# asr9k-mpls-x64-2.0.0.0-r611              asr9k-mpls-x64-2.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-optic-x64-1.0.0.0-r611             asr9k-optic-x64-1.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-ospf-x64-1.0.0.0-r611              asr9k-ospf-x64-1.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-parser-x64-2.0.0.0-r611            asr9k-parser-x64-2.0.0.0-r611.x86_64.rpm-6.1.1
# asr9k-xr-6.1.1                           asr9k-full-x64.iso-6.1.1/asr9k-mini-x64.iso-6.1.1
#

ASR9K_X64_PACKAGES = {
    'asr9k-bgp-x64-\d\.\d\.\d\.\d': 'asr9k-bgp-x64-\d\.\d\.\d\.\d',
    'asr9k-diags-x64-\d\.\d\.\d\.\d': 'asr9k-diags-x64-\d\.\d\.\d\.\d',
    'asr9k-eigrp-x64-\d\.\d\.\d\.\d': 'asr9k-eigrp-x64-\d\.\d\.\d\.\d',
    'asr9k-xr': 'asr9k-full-x64\.iso',
    'asr9k-isis-x64-\d\.\d\.\d\.\d': 'asr9k-isis-x64-\d\.\d\.\d\.\d',
    'asr9k-k9sec-x64-\d\.\d\.\d\.\d': 'asr9k-k9sec-x64-\d\.\d\.\d\.\d',
    'asr9k-li-x64-\d\.\d\.\d\.\d': 'asr9k-li-x64-\d\.\d\.\d\.\d',
    'asr9k-m2m-x64-\d\.\d\.\d\.\d': 'asr9k-m2m-x64-\d\.\d\.\d\.\d',
    'asr9k-mcast-x64-\d\.\d\.\d\.\d': 'asr9k-mcast-x64-\d\.\d\.\d\.\d',
    'asr9k-mgbl-x64-\d\.\d\.\d\.\d': 'asr9k-mgbl-x64-\d\.\d\.\d\.\d',
    'asr9k-xr': 'asr9k-mini-x64\.iso',
    'asr9k-mpls-te-rsvp-x64-\d\.\d\.\d\.\d': 'asr9k-mpls-te-rsvp-x64-\d\.\d\.\d\.\d',
    'asr9k-mpls-x64-\d\.\d\.\d\.\d': 'asr9k-mpls-x64-\d\.\d\.\d\.\d',
    'asr9k-optic-x64-\d\.\d\.\d\.\d': 'asr9k-optic-x64-\d\.\d\.\d\.\d',
    'asr9k-ospf-x64-\d\.\d\.\d\.\d': 'asr9k-ospf-x64-\d\.\d\.\d\.\d',
    'asr9k-parser-x64-\d\.\d\.\d\.\d': 'asr9k-parser-x64-\d\.\d\.\d\.\d'
}

#
# NCS6K:
# Production Images:
# Internal Names:           External Names:
#
# ncs6k-doc-5.2.5           ncs6k-doc.pkg-5.2.5
# ncs6k-li-5.2.5            ncs6k-li.pkg-5.2.5
# ncs6k-xr-5.2.5            ncs6k-mini-x.iso-5.2.5
# ncs6k-full-x.iso-5.2.5
# ncs6k-mcast-5.2.5         ncs6k-mcast.pkg-5.2.5
# ncs6k-mpls-5.2.5          ncs6k-mpls.pkg-5.2.5
# ncs6k-k9sec-5.2.5         ncs6k-k9sec.pkg-5.2.5
# ncs6k-mgbl-5.2.5          ncs6k-mgbl.pkg-5.2.5
# ncs6k-xr.iso-5.2.5

NCS6K_PACKAGES = {
    'ncs6k-doc': 'ncs6k-doc.pkg',
    'ncs6k-li': 'ncs6k-li.pkg',
    'ncs6k-mcast': 'ncs6k-mcast.pkg',
    'ncs6k-mgbl': 'ncs6k-mgbl.pkg',
    'ncs6k-mpls': 'ncs6k-mpls.pkg',
    'ncs6k-k9sec': 'ncs6k-k9sec.pkg',
    'ncs6k-xr': 'ncs6k-mini-x.iso',
}

#
# NCS5K:
# Production Images:
# Internal Names:                 External Names
#
# ncs5k-full-x.iso-6.0.1
# ncs5k-isis-2.0.0.0-r601         ncs5k-isis-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-k9sec-2.0.0.0-r601        ncs5k-k9sec-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-mcast-2.0.0.0-r601        ncs5k-mcast-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-mgbl-3.0.0.0-r601         ncs5k-mgbl-3.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-xr-6.0.1                  ncs5k-mini-x.iso-6.0.1
# ncs5k-mpls-2.0.0.0-r601         ncs5k-mpls-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-ospf-1.0.0.0-r601         ncs5k-ospf-1.0.0.0-r601.x86_64.rpm-6.0.1
#

#
# NCS5500:
# Production Images:
# Internal Names:                      External Names:
#
# ncs5500-eigrp-2.0.0.0-r601           ncs5500-eigrp-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-isis-2.0.0.0-r601            ncs5500-isis-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-k9sec-2.0.0.0-r601           ncs5500-k9sec-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-m2m-2.0.0.0-r601             ncs5500-m2m-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-mgbl-3.0.0.0-r601            ncs5500-mgbl-3.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-xr-6.0.1                     ncs5500-mini-x.iso-6.0.1
# ncs5500-mpls-2.0.0.0-r601            ncs5500-mpls-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-mpls-te-rsvp-2.0.0.0-r601    ncs5500-mpls-te-rsvp-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-ospf-1.0.0.0-r601            ncs5500-ospf-1.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-parser-1.0.0.0-r601          ncs5500-parser-1.0.0.0-r601.x86_64.rpm-6.0.1


def get_target_software_package_list(family, os_type, host_packages, target_version, match_internal_name=False):
    """
    If match_internal_name is true, it matches the host_packages instead of the physical name
    on the server repository.
    """
    target_list = []
    platform_package_list = {}
    target_version_for_iso = ""
    target_version_for_rpm = ""

    if family == PlatformFamily.ASR9K:
        if os_type == "XR":
            platform_package_list = ASR9K_PACKAGES
        elif os_type == "eXR":
            platform_package_list = ASR9K_X64_PACKAGES
            # Internal Names:                 External Names:
            # asr9k-xr-6.1.1                  asr9k-full-x64.iso-6.1.1/asr9k-mini-x64.iso-6.1.1
            # asr9k-mcast-x64-2.0.0.0-r611    asr9k-mcast-x64-2.0.0.0-r611.x86_64.rpm-6.1.1
            target_version_for_iso = target_version + '(?:\.\d+I)?'
            target_version_for_rpm = 'r' + target_version.replace('.', '') + '(?:\d+I)?'
            if not match_internal_name:
                target_version_for_rpm += '\.x86_64\.rpm'

    elif family == PlatformFamily.CRS:
        platform_package_list = CRS_PACKAGES
    elif family == PlatformFamily.NCS6K:
        platform_package_list = NCS6K_PACKAGES

    for k, v in platform_package_list.items():
        for package in host_packages:
            if k in package or re.search(k, package):
                if match_internal_name:
                    target_list.append("{}-{}".format(k, target_version))
                else:
                    if family == PlatformFamily.ASR9K and os_type == "eXR":
                        if "asr9k-xr" in package:
                            target_list.append("{}-{}".format(v, target_version_for_iso))
                        else:
                            target_list.append("{}-{}".format(v, target_version_for_rpm))
                    else:
                        target_list.append("{}-{}".format(v, target_version))

    return target_list
