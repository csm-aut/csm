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


def get_target_software_package_list(family, os_type, host_packages, target_version, match_internal_name=False):
    """
    :param family: The device family
    :param os_type: The device os_type
    :param host_packages: The packages on the device to match with
    :param target_version: The target version
    :param match_internal_name: True or False.  If False, it will match the package external name
    :return: The proposed package list for the targeted software version
    """

    target_list = []
    # ASR9K and ASR9K-64 belong to the same family, but are different software platforms
    software_platform = get_software_platform(family, os_type)

    for host_package in host_packages:
        if '.CSC' in host_package or '.sp' in host_package or 'sysadmin' in host_package:
            continue

        if software_platform in [PlatformFamily.ASR9K, PlatformFamily.CRS]:
            pos = host_package.find('-px')
            if pos == -1:
                continue

            package_name = host_package[0:pos]
            if match_internal_name:
                # asr9k-mgbl-px-5.3.3, hfr-mgbl-px-5.3.3
                target_list.append('{}-px-{}'.format(package_name, target_version))
            else:
                # Handles exceptional case
                if 'asr9k-9000v-nV-px' in host_package:
                    target_list.append('asr9k-asr9000v-nV-px.pie-{}'.format(target_version))
                else:
                    # asr9k-mgbl-px.pie-5.3.3, hfr-mgbl-px.pie-5.3.3
                    target_list.append('{}-px.pie-{}'.format(package_name, target_version))

        elif software_platform in PlatformFamily.NCS6K:
            match = re.search('-\d+\.\d+\.\d+', host_package)
            if not match:
                continue

            package_name = host_package[0:match.start()]
            if match_internal_name:
                if '-xr-' in host_package:
                    # ncs6k-mgbl-5.2.4
                    target_list.append('{}-{}'.format(family.lower() + '-mini-x', target_version))
                else:
                    # ncs6k-mini-x-5.2.4
                    target_list.append('{}-{}'.format(package_name, target_version))
            else:
                if '-xr-' in host_package:
                    # ncs6k-mini-x.iso-5.2.4
                    target_list.append('ncs6k-mini-x.iso-{}'.format(target_version))
                else:
                    # ncs6k-mgbl.pkg-5.2.4
                    target_list.append('{}.pkg-{}'.format(package_name, target_version))

        elif software_platform in [PlatformFamily.ASR9K_64, PlatformFamily.NCS1K,
                                   PlatformFamily.NCS5K, PlatformFamily.NCS5500]:
            # asr9k-xr-6.1.1, ncs5500-xr-6.0.1
            match = re.search('-\d\.\d\.\d.\d', host_package)
            if match:
                # Package other than '-xr-'
                package_name = host_package[0:match.start()]

            if match_internal_name:
                if "-xr" in host_package:
                    if software_platform in [PlatformFamily.NCS1K,
                                             PlatformFamily.NCS5K,
                                             PlatformFamily.NCS5500]:
                        # ncs5k-mini-x-6.1.1
                        target_list.append("{}-{}-{}".format(family.lower(), 'mini-x', target_version))
                    elif software_platform in [PlatformFamily.ASR9K_64]:
                        # asr9k-mini-x64-6.1.1
                        target_list.append("{}-{}-{}".format(family.lower(), 'mini-x64', target_version))
                else:
                    # asr9k-mgbl-x64-3.0.0.0-r601, ncs5k-mgbl-3.0.0.0-r601,
                    target_list.append('{}-{}-{}'.format(package_name, '\d\.\d\.\d.\d',
                                                         'r' + target_version.replace('.', '')))
            else:
                if '-xr-' in host_package:
                    if software_platform in [PlatformFamily.NCS1K,
                                             PlatformFamily.NCS5K,
                                             PlatformFamily.NCS5500]:
                        # ncs5k-mini-x.iso-6.1.1
                        target_list.append("{}-{}-{}".format(family.lower(), 'mini-x.iso', target_version))
                    elif software_platform in [PlatformFamily.ASR9K_64]:
                        # asr9k-mini-x64.iso-6.1.1
                        target_list.append("{}-{}-{}".format(family.lower(), 'mini-x64.iso', target_version))
                else:
                    # asr9k-mgbl-x64-3.0.0.0-r601.x86_64.rpm-6.0.1, ncs5k-mgbl-3.0.0.0-r611.x86_64.rpm-6.1.1
                    target_list.append("{}-{}-{}.{}-{}".format(package_name, '\d\.\d\.\d.\d',
                                                               'r' + target_version.replace('.', ''),
                                                               'x86_64.rpm', target_version))

    return target_list
