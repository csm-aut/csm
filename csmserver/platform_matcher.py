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

"""
For IOS XR, the release string is always after the architecture string  ("-p-" or "-px").

Example,
    input: asr9k-mini-px-4.2.3
           asr9k-px-4.2.3.CSCua16764-1.0.0
           hfr-mini-px-4.2.3
           hfr-px-4.2.3.CSCti75606-1.0.0
    output: 4.2.3
"""
def get_IOSXR_release(name, architecture):
    pos = name.find(architecture)
    if pos != -1:
        partial = name[pos + len(architecture):]
        tokens = partial.split('.')
        if len(tokens) >= 3:
            return tokens[0] + '.' + tokens[1] + '.' + tokens[2]
    return UNKNOWN;

"""
Example,
    input: ncs6k-xr-5.0.1
           ncs6k-5.0.1.CSCul51055-0.0.2.i
           ncs6k-sysadmin-xr-5.0.1
           ncs6k-sysadmin-5.0.1.CSCul51055-0.0.2.i
    output: 5.0.1
"""
def get_NCS6K_release(name, platform_type):
    if platform_type == PLATFORM_TYPE_NCS6K_PACKAGE:
        name = name.replace('ncs6k-xr-', '')
    elif platform_type == PLATFORM_TYPE_NCS6K_SMU:
        name = name.replace('ncs6k-', '')
    elif platform_type == PLATFORM_TYPE_NCS6K_SYSADMIN_PACKAGE:
        name = name.replace('ncs6k-sysadmin-xr-', '')
    elif platform_type == PLATFORM_TYPE_NCS6K_SYSADMIN_SMU:
        name = name.replace('ncs6k-sysadmin-', '')
    
    tokens = name.split('.')
    if len(tokens) >= 3:
        return tokens[0] + '.' + tokens[1] + '.' + tokens[2]
    return UNKNOWN;

def get_platform_type(name):
    for platform_type in pattern_list:
        pattern = pattern_list[platform_type]
        if (pattern.match(name)):
            return platform_type
    
    return PLATFORM_TYPE_UNKNOWN

"""
Returns the platform based on the pattern type.
ASR9K-PX, CRS-PX, NCS6K
"""
def get_platform(name):
    platform_type = get_platform_type(name);
    
    if platform_type == PLATFORM_TYPE_ASR9K_P_SMU or \
       platform_type == PLATFORM_TYPE_ASR9K_P_PACKAGE:
            return PLATFORM_ASR9K_P
    elif platform_type == PLATFORM_TYPE_ASR9K_PX_PACKAGE or \
         platform_type == PLATFORM_TYPE_ASR9K_PX_SMU or \
         platform_type == PLATFORM_TYPE_ASR9K_PX_SP:
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
       platform_type == PLATFORM_TYPE_CRS_P_PACKAGE:
        return get_IOSXR_release(name, "-p-")
    elif platform_type == PLATFORM_TYPE_NCS6K_SMU or \
         platform_type == PLATFORM_TYPE_NCS6K_PACKAGE or \
         platform_type == PLATFORM_TYPE_NCS6K_SYSADMIN_SMU or \
         platform_type == PLATFORM_TYPE_NCS6K_SYSADMIN_PACKAGE:
        return get_NCS6K_release(name, platform_type)
    elif platform_type == PLATFORM_TYPE_ASR9K_PX_PACKAGE or \
         platform_type == PLATFORM_TYPE_ASR9K_PX_SMU or \
         platform_type == PLATFORM_TYPE_ASR9K_PX_SP or \
         platform_type == PLATFORM_TYPE_CRS_PX_SMU or \
         platform_type == PLATFORM_TYPE_CRS_PX_PACKAGE:
        return get_IOSXR_release(name, "-px-")
    else:
        return UNKNOWN;

if __name__ == '__main__':   
    name = 'ncs6k-5.0.1.CSCul51055-0.0.2.i'
    print(get_platform(name), get_release(name))