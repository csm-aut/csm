# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
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
from csm_exceptions.exceptions import UnknownSoftwarePlatform
from parser_factory import IOSXRParserFactory, ASR9KParserFactory, \
    EXRParserFactory, IOSXEParserFactory, IOSParserFactory, NXOSParserFactory


def get_parser_factory(software_platform, os_type):
    if software_platform == PlatformFamily.ASR9K:
        return ASR9KParserFactory()
    elif software_platform == PlatformFamily.XR12K:
        return IOSXRParserFactory()
    elif software_platform == PlatformFamily.CRS:
        return IOSXRParserFactory()
    elif software_platform in [PlatformFamily.NCS1K,
                               PlatformFamily.NCS4K,
                               PlatformFamily.NCS5K,
                               PlatformFamily.NCS540,
                               PlatformFamily.IOSXRv_9K,
                               PlatformFamily.IOSXRv_X64,
                               PlatformFamily.ASR9K_X64,
                               PlatformFamily.NCS6K,
                               PlatformFamily.NCS5500]:
        return EXRParserFactory()
    elif software_platform == PlatformFamily.ASR900:
        if os_type == 'IOS':
            return IOSParserFactory()
        elif os_type == 'XE':
            return IOSXEParserFactory()
        else:
            raise UnknownSoftwarePlatform('%s' % software_platform)
    elif software_platform == PlatformFamily.ASR1K:
        return IOSXEParserFactory()
    elif software_platform == PlatformFamily.N9K:
        return NXOSParserFactory()
    else:
        raise UnknownSoftwarePlatform('%s' % software_platform)