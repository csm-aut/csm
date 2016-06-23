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
from utils import import_class
from constants import PlatformFamily
from csm_exceptions.exceptions import UnknownSoftwarePlatform


def get_package_parser_class(software_platform):
    if software_platform in [PlatformFamily.ASR9K,
                             PlatformFamily.CRS]:
        return import_class('parsers.platforms.IOS-XR.CLIPackageParser')
    elif software_platform in [PlatformFamily.NCS5K,
                               PlatformFamily.NCS6K,
                               PlatformFamily.NCS5500,
                               PlatformFamily.ASR9K_64]:
        return import_class('parsers.platforms.eXR.CLIPackageParser')
    elif software_platform in [PlatformFamily.ASR900]:
        return import_class('parsers.platforms.IOS-XE.CLIPackageParser')
    elif software_platform in [PlatformFamily.N9K]:
        return import_class('parsers.platforms.NX-OS.CLIPackageParser')
    else:
        raise UnknownSoftwarePlatform('%s' % software_platform)


