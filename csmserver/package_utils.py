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
from utils import get_software_platform

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
# Internal Names:                         External Names
#
# ncs5k-full-x.iso-6.0.1
# ncs5k-isis-2.0.0.0-r601                 ncs5k-isis-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-k9sec-2.0.0.0-r601                ncs5k-k9sec-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-mcast-2.0.0.0-r601                ncs5k-mcast-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-mgbl-3.0.0.0-r601                 ncs5k-mgbl-3.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-xr-6.0.1                          ncs5k-mini-x.iso-6.0.1
# ncs5k-mpls-2.0.0.0-r601                 ncs5k-mpls-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5k-ospf-1.0.0.0-r601                 ncs5k-ospf-1.0.0.0-r601.x86_64.rpm-6.0.1
#
# NCS5500:
# Production Images:
# Internal Names:                          External Names:
#
# ncs5500-eigrp-2.0.0.0-r601               ncs5500-eigrp-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-isis-2.0.0.0-r601                ncs5500-isis-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-k9sec-2.0.0.0-r601               ncs5500-k9sec-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-m2m-2.0.0.0-r601                 ncs5500-m2m-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-mgbl-3.0.0.0-r601                ncs5500-mgbl-3.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-xr-6.0.1                         ncs5500-mini-x.iso-6.0.1
# ncs5500-mpls-2.0.0.0-r601                ncs5500-mpls-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-mpls-te-rsvp-2.0.0.0-r601        ncs5500-mpls-te-rsvp-2.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-ospf-1.0.0.0-r601                ncs5500-ospf-1.0.0.0-r601.x86_64.rpm-6.0.1
# ncs5500-parser-1.0.0.0-r601              ncs5500-parser-1.0.0.0-r601.x86_64.rpm-6.0.1

# ASR9K-64
# Engineering Package - Internal Name:     External Name:
# asr9k-mcast-x64-1.0.0.0-r61113I          asr9k-mcast-x64-1.0.0.0-r61113I.x86_64.rpm-6.1.1
#
# Production Package - Internal Name:      External Name:
# asr9k-xr-6.1.1                           asr9k-full-x64.iso-6.1.1/asr9k-mini-x64.iso-6.1.1
# asr9k-mcast-x64-1.0.0.0-r611             asr9k-mcast-x64-1.0.0.0-r611.x86_64.rpm-6.1.1

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

EXR_RPM_PACKAGES = {
    # This list will cover all eXR platforms.  They are arranged in alphabetical order for human consumption.
    '-bgp-x64-\d\.\d\.\d\.\d': '-bgp-x64-\d\.\d\.\d\.\d',
    '-diags-x64-\d\.\d\.\d\.\d': '-diags-x64-\d\.\d\.\d\.\d',
    '-doc-x64-\d\.\d\.\d\.\d': '-diags-x64-\d\.\d\.\d\.\d',
    '-eigrp-x64-\d\.\d\.\d\.\d': '-eigrp-x64-\d\.\d\.\d\.\d',
    '-fwding-x64-\d\.\d\.\d\.\d': '-fwding-x64-\d\.\d\.\d\.\d',
    '-infra-x64-\d\.\d\.\d\.\d': '-infra-x64-\d\.\d\.\d\.\d',
    '-infra-test-x64-\d\.\d\.\d\.\d': '-infra-test-x64-\d\.\d\.\d\.\d',
    '-isis-x64-\d\.\d\.\d\.\d': '-isis-x64-\d\.\d\.\d\.\d',
    '-k9sec-x64-\d\.\d\.\d\.\d': '-k9sec-x64-\d\.\d\.\d\.\d',
    '-li-x64-\d\.\d\.\d\.\d': '-li-x64-\d\.\d\.\d\.\d',
    '-m2m-x64-\d\.\d\.\d\.\d': '-m2m-x64-\d\.\d\.\d\.\d',
    '-mcast-x64-\d\.\d\.\d\.\d': '-mcast-x64-\d\.\d\.\d\.\d',
    '-mgbl-x64-\d\.\d\.\d\.\d': '-mgbl-x64-\d\.\d\.\d\.\d',
    '-xr': '-mini-x64',
    '-mpls-x64-\d\.\d\.\d\.\d': '-mpls-x64-\d\.\d\.\d\.\d',
    '-mpls-te-rsvp-x64-\d\.\d\.\d\.\d': '-mpls-te-rsvp-x64-\d\.\d\.\d\.\d',
    '-optic-x64-\d\.\d\.\d\.\d': '-optic-x64-\d\.\d\.\d\.\d',
    '-ospf-x64-\d\.\d\.\d\.\d': '-ospf-x64-\d\.\d\.\d\.\d',
    '-parser-x64-\d\.\d\.\d\.\d': '-parser-x64-\d\.\d\.\d\.\d',
    '-rm-x64-\d\.\d\.\d\.\d': '-rm-x64-\d\.\d\.\d\.\d',
}


def get_target_software_package_list(family, os_type, host_packages, target_version, match_internal_name=False):
    """
    If match_internal_name is true, it matches the host_packages instead of the physical name
    on the server repository.
    """

    target_list = []
    platform_package_list = {}

    # ASR9K and ASR9K-64 belong to the same family, but are different software platforms
    software_platform = get_software_platform(family, os_type)

    if software_platform == PlatformFamily.ASR9K:
        platform_package_list = ASR9K_PACKAGES
    elif software_platform == PlatformFamily.CRS:
        platform_package_list = CRS_PACKAGES
    elif software_platform == PlatformFamily.NCS6K:
        platform_package_list = NCS6K_PACKAGES
    elif software_platform in [PlatformFamily.ASR9K_64, PlatformFamily.NCS1K,
                               PlatformFamily.NCS5K, PlatformFamily.NCS5500]:
        platform_package_list = EXR_RPM_PACKAGES
        for host_package in host_packages:
            for internal_name, external_name in platform_package_list.items():
                if software_platform in [PlatformFamily.ASR9K, PlatformFamily.CRS, PlatformFamily.NCS6K]:
                    if internal_name in host_package:
                        if match_internal_name:
                            target_list.append("{}-{}".format(internal_name, target_version))
                        else:
                            target_list.append("{}-{}".format(external_name, target_version))
                        break

                elif software_platform in [PlatformFamily.ASR9K_64, PlatformFamily.NCS1K,
                                           PlatformFamily.NCS5K, PlatformFamily.NCS5500]:
                    # Add family prefix
                    package_name = family.lower() + internal_name

                    # Further refining, for these platforms, 'x64-' is not applicable
                    if software_platform in [PlatformFamily.NCS1K, PlatformFamily.NCS5K, PlatformFamily.NCS5500]:
                        package_name = package_name.replace('-x64', '')

                    if re.search(package_name, host_package):
                        if match_internal_name:
                            if "-xr" in host_package:
                                if software_platform in [PlatformFamily.NCS1K, PlatformFamily.NCS5K,
                                                         PlatformFamily.NCS5500]:
                                    # Unlike ASR9K-64, these platforms have two separate packages
                                    # ncs5k-xr-6.0.1 and ncs5k-sysadmin-6.0.1
                                    target_list.append("{}-{}".format(family.lower() + '-xr', target_version))
                                    target_list.append("{}-{}".format(family.lower() + '-sysadmin', target_version))
                                elif software_platform in [PlatformFamily.ASR9K_64]:
                                    # asr9k-mini-x64-6.1.1
                                    target_list.append("{}-{}".format(family.lower() + '-mini-x64', target_version))
                            else:
                                target_list.append("{}-{}".format(package_name,
                                                                  'r' + target_version.replace('.', '')))
                        else:
                            # Produce the ISO image name
                            if "-xr" in host_package:
                                if software_platform in [PlatformFamily.NCS1K, PlatformFamily.NCS5K,
                                                         PlatformFamily.NCS5500]:
                                    # ncs5k-mini-x.iso-6.1.1
                                    target_list.append("{}-{}".format(family.lower() + '-mini-x.iso', target_version))
                                elif software_platform in [PlatformFamily.ASR9K_64]:
                                    # asr9k-mini-x64.iso-6.1.1
                                    target_list.append("{}-{}".format(family.lower() + '-mini-x64.iso', target_version))
                            else:
                                # ncs5k-mgbl-3.0.0.0-r611.x86_64.rpm-6.1.1
                                target_list.append("{}-{}{}-{}".format(package_name,
                                                                       'r' + target_version.replace('.', ''),
                                                                       '.x86_64.rpm', target_version))
                        break

    return target_list
