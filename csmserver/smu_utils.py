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
from constants import PackageType
from platform_matcher import get_platform, get_release, UNKNOWN
from smu_info_loader import SMUInfoLoader
from smu_advisor import get_excluded_supersede_list 
from smu_advisor import get_missing_required_prerequisites
from smu_advisor import get_dict_from_list

SMU_INDICATOR = 'CSC'
SP_INDICATOR = '.sp'
    
"""
Returns the package type.  Available package types are defined in PackageType.
"""
def get_package_type(name):
    """
    Only ASR9K supports Service Packs concept
    Example: asr9k-px-4.3.2.sp-1.0.0 or asr9k-px-4.3.2.k9-sp-1.0.0
    """
    if name.find(SMU_INDICATOR) != -1:
        return PackageType.SMU
    elif name.find(SP_INDICATOR) != -1:
        return PackageType.SERVICE_PACK
    else:
        return PackageType.PACKAGE
    
"""
Given a package name, try to derive a name which can be used to lookup a SMU or SP
in the SMU meta file.
 
However, there is no guarantee that the correct name can be derived. That depends
on the given name if it is within the parsing criteria.
"""
def get_smu_lookup_name(name):
    name = name.strip()
    package_type = get_package_type(name)
    if package_type != PackageType.SMU and package_type != PackageType.SERVICE_PACK:
        return name
    
    # The worst case scenario of the name could be "disk0:asr9k-px-4.2.1.CSCud90009-1.0.0.pie"
    name = name.replace('.pie','')
    
    # Skip the location string if found
    pos = name.find(':')
    if pos != -1:
        name = name[pos+1:]
        
    # For SMU, the resultant name needs to be in this format: "asr9k-px-4.2.1.CSCud90009".
    # However, on the device, the SMU is in this format: "asr9k-px-4.2.1.CSCud90009-1.0.0".
    pos = name.find(SMU_INDICATOR)
    if pos != -1:
        # Strip the -1.0.0 string if found
        try:
            # index may throw ValueError if substring not found
            pos2 = name.index('-', pos)
            if pos2 != -1:
                name = name[:pos2]
        except:
            pass
            
    return name

"""
The smu_info_dict has the following format
   smu name ->  set()
"""
def get_unique_set_from_dict(smu_info_dict):
    resultant_set = set()
    for smu_set in smu_info_dict.values():
        for smu_name in smu_set:
            if smu_name not in resultant_set:
                resultant_set.add(smu_name)
            
    return resultant_set
                
def get_missing_prerequisite_list(smu_list):
    result_list = []   
    platform, release = get_platform_and_release(smu_list)
    
    if platform == UNKNOWN or release == UNKNOWN:
        return result_list
    
    # Load the SMU information
    smu_loader = SMUInfoLoader(platform, release)
    smu_info_list= []
    smu_name_set = set()
    
    for line in smu_list:
        smu_name = get_smu_lookup_name(line)
        smu_info = smu_loader.get_smu_info(smu_name)
        
        if smu_info is None or smu_name in smu_name_set:  
            continue

        smu_name_set.add(smu_name)
        smu_info_list.append(smu_info)
        
    if len(smu_info_list) > 0:
        # Exclude all the superseded SMUs in smu_info_list
        excluded_supersede_list = get_excluded_supersede_list(smu_info_list)
       
        missing_required_prerequisite_dict = \
            get_missing_required_prerequisites(smu_loader, excluded_supersede_list)
        
        missing_required_prerequisite_set = get_unique_set_from_dict(missing_required_prerequisite_dict)
        for pre_requisite_smu in missing_required_prerequisite_set:
            result_list.append(pre_requisite_smu + '.' + smu_loader.file_suffix)
                
    return result_list

"""
Given a package list (SMU/SP/Pacages), return the platform and release.
"""
def get_platform_and_release(package_list):
    platform = UNKNOWN
    release = UNKNOWN
    
    # Identify the platform and release
    for line in package_list:
        platform = get_platform(line)
        release = get_release(line)
        
        if platform != UNKNOWN and release != UNKNOWN:
            break
        
    return platform, release

"""
Given a SMU list, return a dictionary which contains
key: smu name in smu_list
value: cco filename  (can be None if smu_name is not in the XML file)
""" 
def get_download_info_dict(smu_list):
    download_info_dict = {}
    platform, release = get_platform_and_release(smu_list)
    
    if platform == UNKNOWN or release == UNKNOWN:
        return download_info_dict, None
    
    # Load the SMU information
    smu_loader = SMUInfoLoader(platform, release)
    for smu_name in smu_list:
        lookup_name = get_smu_lookup_name(smu_name)
        smu_info = smu_loader.get_smu_info(lookup_name)
        if smu_info is not None:
            # Return back the same name (i.e. smu_name)
            download_info_dict[smu_name] = smu_info.cco_filename
        else:
            download_info_dict[smu_name] = None
            
    return download_info_dict, smu_loader
    
"""
Returns the validated list given the SMU/SP list.
A smu_list may contain packages, SMUs, SPs, or junk texts.
"""
def get_validated_list(smu_list):
    unrecognized_list = []
    package_list = []
    result_list = []
    
    # Identify the platform and release
    platform, release = get_platform_and_release(smu_list)
    
    if platform == UNKNOWN or release == UNKNOWN:
        for line in smu_list:
            result_list.append({'smu_entry': line, 'is':'Unrecognized' })
        return result_list
    
    # Load the SMU information
    smu_loader = SMUInfoLoader(platform, release)
    
    file_suffix = smu_loader.file_suffix
    smu_info_list= []
    smu_name_set = set()
    
    for line in smu_list:
        smu_name = get_smu_lookup_name(line)
        smu_info = smu_loader.get_smu_info(smu_name)
        
        if smu_info is None:
            # Check if the entry is a package type
            if get_platform(smu_name) == UNKNOWN:
                unrecognized_list.append(smu_name)
            else:
                package_list.append(smu_name)
            continue
        
        if smu_name in smu_name_set:
            continue
    
        smu_name_set.add(smu_name)
        smu_info_list.append(smu_info)
        
    if len(smu_info_list) > 0:
        # Exclude all the superseded SMUs in smu_info_list
        excluded_supersede_list = get_excluded_supersede_list(smu_info_list)
       
        missing_required_prerequisite_dict = \
            get_missing_required_prerequisites(smu_loader, excluded_supersede_list)
        
        missing_required_prerequisite_set = get_unique_set_from_dict(missing_required_prerequisite_dict)
        for pre_requisite_smu in missing_required_prerequisite_set:
            pre_requisite_smu_info = smu_loader.get_smu_info(pre_requisite_smu)
            description = pre_requisite_smu_info.description if pre_requisite_smu_info is not None else ''
            result_list.append({ 'smu_entry': pre_requisite_smu + '.' + file_suffix, 'is':'Pre-requisite', 'description':description })
                
        excluded_supersede_dict = get_dict_from_list(excluded_supersede_list)
        
        for smu_info in smu_info_list:
            if smu_info.name not in excluded_supersede_dict:
                result_list.append({'smu_entry': smu_info.name + '.' + file_suffix, 'is':'Superseded', 'description':smu_info.description })
            else:
                result_list.append({'smu_entry': smu_info.name + '.' + file_suffix, 'is':'SMU/SP', 'description':smu_info.description })
    
    if len(package_list) > 0:
        for entry in package_list:
            result_list.append({'smu_entry': entry, 'is':'Package', 'description':'' })
            
    if len(unrecognized_list) > 0:
        for entry in unrecognized_list:
            result_list.append({'smu_entry': entry, 'is':'Unrecognized', 'description':'' })
 
            
    return result_list

if __name__ == '__main__':
    pass