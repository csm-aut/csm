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
from utils import replace_multiple


def get_target_software_package_list(family, os_type, host_packages, target_version, return_internal_name=False):
    """
    Given a list of host packages in the device active package area and a target software version to upgrade to,
    this method returns a list of recommended external or internal filenames.

    When ncs5500-mini-x.iso-6.1.3 is added successfully to the device, it will be shown as ncs5k-mini-x-6.1.3 in the
    device inactive package area.  Once it is activated, it becomes ncs5500-sysadmin-6.1.3 and ncs5500-xr-6.1.3.

    :param family: The device family
    :param os_type: The device os_type
    :param host_packages: The packages on the device to match with
    :param target_version: The target version
    :param return_internal_name: True or False.  If False, it will return the package external name
    :return: The proposed package list for the targeted software version
    """
    target_list = []

    numeric_target_version = get_3_digit_numeric_version(target_version)
    # ASR9K and ASR9K-X64 belong to the same family, but are different software platforms
    software_platform = get_software_platform(family, os_type)

    for host_package in host_packages:
        if '.CSC' in host_package or '.sp' in host_package or 'sysadmin' in host_package:
            continue

        if software_platform in [PlatformFamily.ASR9K, PlatformFamily.XR12K, PlatformFamily.CRS]:
            """
            External Names:                            Internal Names (i.e. host_package):
            asr9k-mcast-px.pie-6.1.1                   asr9k-mcast-px-6.2.2
            hfr-mcast-px.pie-6.1.1                     asr9k-mcast-px-6.2.2
            hfr-asr9000v-nV-px.pie-6.1.1               hfr-asr9000v-nV-px-6.2.2

            These two packages cause CSM headache because of different formatting compared to other packages.
            asr9k-services-infra-px.pie-6.1.1          asr9k-services-infra-6.2.2
            asr9k-asr9000v-nV-px.pie-6.1.1             asr9k-9000v-nV-px-6.2.2
            """
            pos = host_package.rfind('-')
            if pos != -1:
                if return_internal_name:
                    target_list.append('{}-{}'.format(host_package[0:pos], target_version))
                else:
                    # Handles exceptional cases
                    if 'asr9k-9000v-nV-px' in host_package:
                        target_list.append('asr9k-asr9000v-nV-px.pie-{}'.format(target_version))
                    elif 'asr9k-services-infra' in host_package:
                        target_list.append('asr9k-services-infra-px.pie-{}'.format(target_version))
                    else:
                        # asr9k-mgbl-px.pie-5.3.3, hfr-mgbl-px.pie-5.3.3
                        target_list.append('{}.pie-{}'.format(host_package[0:pos], target_version))

        elif software_platform == PlatformFamily.NCS4K or \
                (software_platform == PlatformFamily.NCS6K and numeric_target_version < 631):
            """
            NCS6K: Pre-6.3.1:
                External Name:                                Internal Name:
                ncs6k-mcast.pkg-6.1.2                         ncs6k-mcast-6.1.2
                ncs6k-full-x.iso-6.1.2 or                     ncs6k-sysadmin-6.1.2
                ncs6k-mini-x.iso-6.1.2                        ncs6k-xr-6.1.2
            """
            match = re.search('-\d+\.\d+\.\d+', host_package)
            if not match:
                continue

            package_name = host_package[0:match.start()]
            if return_internal_name:
                if '-xr-' in host_package:
                    # ncs6k-mini-x-6.3.0
                    target_list.append('{}-mini-x-{}'.format(family.lower(), target_version))
                else:
                    # ncs6k-mcast-6.3.0
                    target_list.append('{}-{}'.format(package_name, target_version))
            else:
                if '-xr-' in host_package:
                    # ncs6k-mini-x.iso-5.2.4
                    # ncs4k-mini-x.iso-6.0.2
                    if software_platform in [PlatformFamily.NCS6K]:
                        target_list.append('ncs6k-mini-x.iso-{}'.format(target_version))
                    elif software_platform in [PlatformFamily.NCS4K]:
                        target_list.append('ncs4k-mini-x.iso-{}'.format(target_version))
                    else:
                        # to add new platforms in the future
                        pass
                else:
                    # ncs6k-mgbl.pkg-5.2.4
                    # ncs4k-mgbl.pkg-6.0.2
                    target_list.append('{}.pkg-{}'.format(package_name, target_version))

        elif software_platform in [PlatformFamily.ASR9K_X64, PlatformFamily.NCS1K,
                                   PlatformFamily.NCS5K, PlatformFamily.NCS5500] or \
                (software_platform == PlatformFamily.NCS6K and numeric_target_version >= 631):
            """
            NCS6K: 6.3.1 and Later:
            External Name:                                Internal Name:
            ncs6k-mcast-1.0.0.0-r63134I.x86_64.rpm        ncs6k-mcast-1.0.0.0-r63134I (Engineering Package)
            ncs6k-mcast-1.0.0.0-r631.x86_64.rpm           ncs6k-mcast-1.0.0.0-r631
            ncs6k-full-x-6.3.1.iso or                     ncs6k-sysadmin-6.3.1
            ncs6k-mini-x-6.3.1.iso                        ncs6k-xr-6.3.1

            NCS5500:
            External Name:                                Internal Name:
            ncs5500-mcast-1.0.0.0-r63134I.x86_64.rpm      ncs5500-mcast-1.0.0.0-r63134I (Engineering Package)
            ncs5500-mcast-2.0.0.0-r613.x86_64.rpm         ncs5500-mcast-2.0.0.0-r613
            ncs5500-mini-x.iso-6.1.3                      ncs5500-sysadmin-6.1.3
                                                          ncs5500-xr-6.1.3

            ASR9K-X64:
            External Name:                                Internal Name:
            asr9k-mcast-x64-2.0.0.0-r613.x86_64.rpm       asr9k-mcast-x64-2.0.0.0-r613
            asr9k-full-x64-6.1.3.iso  or                  asr9k-sysadmin-6.1.3
            asr9k-mini-x64-6.1.3.iso                      asr9k-xr-6.1.3
            """
            # Extract the package name (except the '-xr-' package) by searching for '-x.x.x.x'.
            match = re.search('-\d\.\d\.\d.\d', host_package)
            if match:
                package_name = host_package[0:match.start()]

            if return_internal_name:
                if "-xr" in host_package:
                    if software_platform in [PlatformFamily.NCS1K,
                                             PlatformFamily.NCS5K,
                                             PlatformFamily.NCS5500,
                                             PlatformFamily.NCS6K]:
                        # ncs5k-mini-x-6.1.3 (this name is in the device inactive package area)
                        target_list.append("{}-mini-x-{}".format(family.lower(), target_version))
                    elif software_platform in [PlatformFamily.ASR9K_X64]:
                        # asr9k-mini-x64-6.1.3 (this name is in the device inactive package area)
                        target_list.append("{}-mini-x64-{}".format(family.lower(), target_version))
                else:
                    # asr9k-mgbl-x64-3.0.0.0-r613, ncs5k-mgbl-3.0.0.0-r613,
                    target_list.append('{}-{}-{}'.format(package_name, '\d\.\d\.\d.\d',
                                                         'r' + target_version.replace('.', '')))
            else:
                if '-xr-' in host_package:
                    if software_platform in [PlatformFamily.NCS1K,
                                             PlatformFamily.NCS5K,
                                             PlatformFamily.NCS5500]:
                        # ncs5k-mini-x.iso-6.1.3
                        target_list.append("{}-{}-{}".format(family.lower(), 'mini-x.iso', target_version))
                    elif software_platform in [PlatformFamily.NCS6K]:
                        # ncs6k-mini-x-6.3.1.iso
                        target_list.append("{}-{}-{}.iso".format(family.lower(), 'mini-x', target_version))
                    elif software_platform in [PlatformFamily.ASR9K_X64]:
                        # asr9k-mini-x64-6.1.3.iso
                        target_list.append("{}-{}-{}.iso".format(family.lower(), 'mini-x64', target_version))
                else:
                    # asr9k-mgbl-x64-3.0.0.0-r613.x86_64.rpm, ncs5k-mgbl-3.0.0.0-r613.x86_64.rpm
                    target_list.append("{}-{}-{}.x86_64.rpm".format(package_name, '\d\.\d\.\d.\d',
                                                                    'r' + target_version.replace('.', '')))

    return target_list


def get_matchable_package_dict(software_packages):
    """
    Given a list of software packages, return the portion of the package name that can be used for internal packaging
    name matching.  This is because the package's external name is different from the package's internal name.

    External Name: ncs5k-mgbl-3.0.0.0-r611.x86_64.rpm
    Internal Name: ncs5k-mgbl-3.0.0.0-r611

    External Name: asr9k-mgbl-px.pie-6.1.1
    Internal Name: asr9k-mgbl-px-6.1.1

    External Name: asr9k-px-5.3.4.CSCvd78405.pie
    Internal Name: asr9k-px-5.3.4.CSCvd78405-1.0.0

    Unfortunately, some of the software packages have different external name and internal name (after activation)
    External Name: asr9k-asr9000v-nV-px.pie-6.1.2
    Internal Name: asr9k-9000v-nV-px-6.1.2

    External Name: asr9k-services-infra-px.pie-5.3.4
    Internal Name: asr9k-services-infra.pie-5.3.4

    Returns a dictionary with key = software_profile_package, value = refined package_name_to_match
    """
    result_dict = dict()

    for software_package in software_packages:
        # FIXME: Need platform specific logic
        package_name_to_match = strip_smu_file_extension(software_package).replace('.x86_64', '')

        if 'asr9000v' in package_name_to_match:
            package_name_to_match = package_name_to_match.replace('asr9000v', '9000v')
        elif 'services-infra-px' in package_name_to_match:
            package_name_to_match = package_name_to_match.replace('-px', '')

        result_dict[software_package] = package_name_to_match

    return result_dict


def is_file_acceptable_for_install_add(filename):
    """
    ASR9K, CRS: .pie, .tar
    NCS6K: .smu, .iso, .pkg, .tar
    NCS4K: .iso .pkg
    ASR9K-X64: .iso, .rpm, .tar
    ASR900: .bin
    """
    acceptable_file_types = ['.pie', '.rpm', '.tar', '.smu', '.iso', '.pkg', '.bin']
    return any(ext in filename for ext in acceptable_file_types)


def is_external_file_a_smu(filename):
    return 'CSC' in filename and (filename.endswith('.pie') or filename.endswith('.smu'))


def is_external_file_a_release_software(filename):
    return '-iosxr-' in filename and filename.endswith('.tar')


def strip_smu_file_extension(filename):
    return replace_multiple(filename, {'.pie': '', '.smu': '', '.rpm': ''})


def get_3_digit_numeric_version(version_string):
    version_string = ''.join(c for c in version_string if c not in 'r.I')
    try:
        if len(version_string) >= 3:
            return int(version_string[:3])
    except ValueError:
        pass

    return -1


def get_numeric_xr_version(package_name):
    """
    :param package_name:
    :return: A 3 digit numeric version or -1
    """
    # r61117I or r611 or 6.1.1.17I or 6.1.1 or 6.1.1.22I
    version_re = re.compile("(?P<VERSION>(r\d+\d+\d+(\d+\w+)?)|(\d+\.\d+\.\d+(\.\d+\w+)?)(?!\.\d)(?!-))")
    result = re.search(version_re, package_name)
    if result:
        version_string = ''.join(c for c in result.group("VERSION") if c not in 'r.I')
        try:
            if len(version_string) >= 3:
                return int(version_string[:3])
        except ValueError:
            pass

    return -1

if __name__ == '__main__':
    """
    Starting 6.3.1, NCS6K supports eXR package format.
    Pre-6.3.1:
        External Name:                                Internal Name:
        ncs6k-mcast.pkg-6.1.2                         ncs6k-mcast-6.1.2
        ncs6k-full-x.iso-6.1.2 or                     ncs6k-sysadmin-6.1.2
        ncs6k-mini-x.iso-6.1.2                        ncs6k-xr-6.1.2
    6.3.1 and Later:
        External Name:                                Internal Name:
        ncs6k-mcast-1.0.0.0-r63134I.x86_64.rpm        ncs6k-mcast-1.0.0.0-r63134I (Engineering Package)
        ncs6k-mcast-1.0.0.0-r631.x86_64.rpm           ncs6k-mcast-1.0.0.0-r631
        ncs6k-full-x-6.3.1.iso or                     ncs6k-sysadmin-6.3.1
        ncs6k-mini-x-6.3.1.iso                        ncs6k-xr-6.3.1
    """
    to_match = 'ncs6k-mini-x.iso-6.1.2'                   # 6.1.2
    to_match = 'ncs6k-mcast-1.0.0.0-r63134I.x86_64.rpm'   # r63134I
    to_match = 'ncs6k-mcast-1.0.0.0-r631.x86_64.rpm'      # r631
    to_match = 'ncs6k-mcast.pkg-6.1.2'                    # 6.1.2
    to_match = 'ncs6k-mcast.pkg-6.1.2.34I'                # 6.1.2.34I

    print(get_numeric_xr_version(to_match))

    print('3 digit version', get_3_digit_numeric_version('6.1.3.14I'))

