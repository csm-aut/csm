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

UNKNOWN = "unknown"

PLATFORM_ASR9K_P = 'asr9k_p'
PLATFORM_ASR9K_PX = "asr9k_px"
PLATFORM_CRS_P = "crs_p"
PLATFORM_CRS_PX = "crs_px"
PLATFORM_NCS6K = "ncs6k"
PLATFORM_NCS6K_SYSADMIN = "ncs6k_sysadmin"

PLATFORM_TYPE_UNKNOWN  = -1

# IOS XR
PLATFORM_TYPE_ASR9K_PX_SMU = 0
PLATFORM_TYPE_ASR9K_PX_SP = 1
PLATFORM_TYPE_ASR9K_P_SMU = 2
PLATFORM_TYPE_ASR9K_P_PACKAGE = 3
PLATFORM_TYPE_ASR9K_PX_PACKAGE = 4
PLATFORM_TYPE_CRS_PX_SMU = 5
PLATFORM_TYPE_CRS_P_SMU = 6
PLATFORM_TYPE_CRS_PX_PACKAGE = 7
PLATFORM_TYPE_CRS_P_PACKAGE = 8

PLATFORM_TYPE_ASR9K_PX_TAR = 13

"""
Match NCS6K_SMU before NS6K_PACKAGE so a SMU won't 
be treated as a package as they have a very similar format.
In addition, the long string (ncs6k-sysadmin) is matched first.
"""
PLATFORM_TYPE_NCS6K_SYSADMIN_SMU = 9;         
PLATFORM_TYPE_NCS6K_SYSADMIN_PACKAGE = 10;    
PLATFORM_TYPE_NCS6K_SMU = 11;         
PLATFORM_TYPE_NCS6K_PACKAGE = 12;

pattern_list = {}

# disk0:asr9k-mini-p-4.2.1
pattern = re.compile("\\S*asr9k-\\S*-p(-\\d+\\.\\d+\\.\\d+)\\S*")
pattern_list[PLATFORM_TYPE_ASR9K_P_PACKAGE] = pattern

# disk0:asr9k-p-4.2.3.CSCtz89449
pattern = re.compile("\\S*asr9k-p(-\\d+\\.\\d+\\.\\d+\\.)CSC\\S*")
pattern_list[PLATFORM_TYPE_ASR9K_P_SMU] = pattern

# disk0:asr9k-mini-px-4.2.1
pattern = re.compile("\\S*asr9k-\\S*-px(-\\d+\\.\\d+\\.\\d+)\\S*")
pattern_list[PLATFORM_TYPE_ASR9K_PX_PACKAGE] = pattern

# disk0:asr9k-px-4.2.3.CSCtz89449
pattern = re.compile("\\S*asr9k-px(-\\d+\\.\\d+\\.\\d+\\.)CSC\\S*")
pattern_list[PLATFORM_TYPE_ASR9K_PX_SMU] = pattern

# ASR9K-iosxr-px-k9-5.3.0.tar or ASR9K-iosxr-px-5.3.1-bridge_smus.tar
pattern = re.compile("\\S*ASR9K-iosxr-px\\S*(-\\d+\\.\\d+\\.\\d+)\\S*\\.tar")
pattern_list[PLATFORM_TYPE_ASR9K_PX_TAR] = pattern

# disk0:asr9k-px-4.3.2.sp-1.0.0 or asr9k-px-4.3.2.k9-sp-1.0.0
pattern = re.compile("\\S*asr9k-px(-\\d+\\.\\d+\\.\\d+\\.)\\S*sp\\S*")
pattern_list[PLATFORM_TYPE_ASR9K_PX_SP] = pattern

# disk0:hfr-mini-px-4.2.1
pattern = re.compile("\\S*hfr-\\S*-px(-\\d+\\.\\d+\\.\\d+)\\S*")
pattern_list[PLATFORM_TYPE_CRS_PX_PACKAGE] = pattern

# disk0:hfr-px-4.2.3.CSCtz89449
pattern = re.compile("\\S*hfr-px(-\\d+\\.\\d+\\.\\d+\\.)CSC\\S*")
pattern_list[PLATFORM_TYPE_CRS_PX_SMU] =  pattern

# disk0:hfr-p-4.2.3.CSCtz89449
pattern = re.compile("\\S*hfr-p(-\\d+\\.\\d+\\.\\d+\\.)CSC\\S*")
pattern_list[PLATFORM_TYPE_CRS_P_SMU] = pattern

# disk0:hfr-mini-p-4.2.1
pattern = re.compile("\\S*hfr-\\S*-p(-\\d+\\.\\d+\\.\\d+)\\S*")
pattern_list[PLATFORM_TYPE_CRS_P_PACKAGE] = pattern

# ncs6k-5.0.1.CSCul51055-0.0.2.i
pattern = re.compile("\\S*ncs6k(-\\d+\\.\\d+\\.\\d+\\.)CSC\\S*")
pattern_list[PLATFORM_TYPE_NCS6K_SMU] = pattern

# ncs6k-mcast-5.0.1
pattern = re.compile("\\S*ncs6k-\\S*(-\\d+\\.\\d+\\.\\d+)\\S*")
pattern_list[PLATFORM_TYPE_NCS6K_PACKAGE] = pattern

# ncs6k-sysadmin-5.0.0.CSCul30161
pattern = re.compile("\\S*ncs6k-sysadmin(-\\d+\\.\\d+\\.\\d+\\.)CSC\\S*")
pattern_list[PLATFORM_TYPE_NCS6K_SYSADMIN_SMU] = pattern

# ncs6k-sysadmin-mcast-5.0.1
pattern = re.compile("\\S*ncs6k-sysadmin-\\S*(-\\d+\\.\\d+\\.\\d+)\\S*")
pattern_list[PLATFORM_TYPE_NCS6K_SYSADMIN_PACKAGE] = pattern


def get_IOSXR_release(name):
    matches = re.findall("\d+\.\d+\.\d+", name)
    if matches:
        return matches[0]
    return UNKNOWN


def get_NCS6K_release(name):
    """
    Example,
        input: ncs6k-xr-5.0.1
               ncs6k-5.0.1.CSCul51055-0.0.2.i
               ncs6k-sysadmin-xr-5.0.1
               ncs6k-sysadmin-5.0.1.CSCul51055-0.0.2.i
               ASR9K-iosxr-px-k9-5.0.1.tar
               ASR9K-iosxr-px-5.0.1-bridge_smus.tar
        output: 5.0.1

    """
    matches = re.findall("\d+\.\d+\.\d+", name)
    if matches:
        return matches[0]
    return UNKNOWN


def get_platform_type(name):
    for platform_type in pattern_list:
        pattern = pattern_list[platform_type]
        if pattern.match(name):
            return platform_type
    
    return PLATFORM_TYPE_UNKNOWN


def get_platform(name):
    """
    Returns the platform based on the pattern type.
    ASR9K-PX, CRS-PX, NCS6K
    """
    platform_type = get_platform_type(name)

    if platform_type == PLATFORM_TYPE_ASR9K_P_SMU or \
       platform_type == PLATFORM_TYPE_ASR9K_P_PACKAGE:
            return PLATFORM_ASR9K_P
    elif platform_type == PLATFORM_TYPE_ASR9K_PX_PACKAGE or \
         platform_type == PLATFORM_TYPE_ASR9K_PX_SMU or \
         platform_type == PLATFORM_TYPE_ASR9K_PX_SP or \
         platform_type == PLATFORM_TYPE_ASR9K_PX_TAR:
            return PLATFORM_ASR9K_PX
    elif platform_type == PLATFORM_TYPE_CRS_PX_SMU or \
         platform_type == PLATFORM_TYPE_CRS_PX_PACKAGE:
            return PLATFORM_CRS_PX
    elif platform_type == PLATFORM_TYPE_CRS_P_SMU or \
         platform_type == PLATFORM_TYPE_CRS_P_PACKAGE:
            return PLATFORM_CRS_P
    elif platform_type == PLATFORM_TYPE_NCS6K_SMU or \
         platform_type == PLATFORM_TYPE_NCS6K_PACKAGE:
            return PLATFORM_NCS6K
    elif platform_type == PLATFORM_TYPE_NCS6K_SYSADMIN_SMU or \
         platform_type == PLATFORM_TYPE_NCS6K_SYSADMIN_PACKAGE:
            return PLATFORM_NCS6K_SYSADMIN
    else:
        return UNKNOWN


def get_release(name):
    platform_type = get_platform_type(name)   

    if platform_type == PLATFORM_TYPE_ASR9K_P_SMU or \
        platform_type == PLATFORM_TYPE_ASR9K_P_PACKAGE or \
        platform_type == PLATFORM_TYPE_CRS_P_SMU or \
        platform_type == PLATFORM_TYPE_CRS_P_PACKAGE or \
        platform_type == PLATFORM_TYPE_ASR9K_PX_PACKAGE or \
        platform_type == PLATFORM_TYPE_ASR9K_PX_SMU or \
        platform_type == PLATFORM_TYPE_ASR9K_PX_SP or \
        platform_type == PLATFORM_TYPE_CRS_PX_SMU or \
        platform_type == PLATFORM_TYPE_CRS_PX_PACKAGE or \
        platform_type == PLATFORM_TYPE_ASR9K_PX_TAR:
        return get_IOSXR_release(name)
    elif platform_type == PLATFORM_TYPE_NCS6K_SMU or \
         platform_type == PLATFORM_TYPE_NCS6K_PACKAGE or \
         platform_type == PLATFORM_TYPE_NCS6K_SYSADMIN_SMU or \
         platform_type == PLATFORM_TYPE_NCS6K_SYSADMIN_PACKAGE:
        return get_NCS6K_release(name)
    else:
        return UNKNOWN;

if __name__ == '__main__':   
    names = []
    names.append('ASR9K-iosxr-px-k9-5.3.1.tar')
    names.append('ASR9K-iosxr-px-5.3.1-bridge_smus.tar')
    names.append('asr9k-px-5.3.1.CSCuv00898.pie')
    names.append('ASR9K-iosxr-px-k9-5.1.3.tar')
    names.append('asr9k-px-5.1.3.CSCuw01943.pie')
    names.append('ASR9K-iosxr-px-k9-5.3.0.tar')
    names.append('ASR9K-iosxr-px-5.3.0-turboboot.tar')
    names.append('ASR9K-iosxr-px-5.30.0.tar')
    names.append('asr9k-px-5.2.2.sp1.pie')

    for name in names:
      print name
      print(get_platform(name), get_release(name))
      print