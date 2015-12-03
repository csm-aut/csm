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
from utils import comma_delimited_str_to_list

"""
Returns a list of SMUInfo which has already excluded all the supersedes and included 
missing pre-requisites.
"""
def get_smus_exclude_supersedes_include_prerequisites(smu_loader, smu_info_list):
    smu_info = []
    resultant_smu_dict = {}
    
    for smu_info in smu_info_list:
        if smu_info.status != 'Posted':
            continue
        # Filter out all the superseded SMUs
        superseded_by = comma_delimited_str_to_list(smu_info.superseded_by) 
        if len(superseded_by) == 0:
            resultant_smu_dict[smu_info.name] = smu_info
            
    # Includes all the missing required pre-requisites
    missing_required_prerequisite_set = \
        get_missing_required_prerequisite_set(smu_loader, resultant_smu_dict.values())
        
    for missing_required_prerequisite in missing_required_prerequisite_set:
        if missing_required_prerequisite not in resultant_smu_dict:
            smu_info = smu_loader.get_smu_info(smu_info)
            if smu_info is not None:
                resultant_smu_dict[smu_info.name] = smu_info
    
    return resultant_smu_dict.values()
            
"""
Given a SMU list, returns all the pre-requisites.
"""
def get_missing_required_prerequisite_set(smu_loader, smu_info_list):
    # Dictionary: String:Set
    missing_required_prerequisites_dict = get_missing_required_prerequisites(smu_loader, smu_info_list)
        
    missing_required_prerequisite_set = set()
    for smu_name in missing_required_prerequisites_dict:
        prerequisite_set = missing_required_prerequisites_dict[smu_name]
        for prerequisite in prerequisite_set:
            if prerequisite not in missing_required_prerequisite_set:
                missing_required_prerequisite_set.add(prerequisite)
        
    return missing_required_prerequisite_set

"""
Given a SMUInfo array, returns a dictionary keyed by the SMU name with SMUInfo as the value.
"""
def get_dict_from_list(smu_info_list):
    smu_info_dict = {}
    
    for smu_info in smu_info_list:
        smu_info_dict[smu_info.name] = smu_info
        
    return smu_info_dict

"""
Given a SMUInfo list, return all the missing pre-requisites in a dictionary.
If a pre-requisite is superseded by a SMU in the smu_info_list, it is not
considered a missing pre-requisite.  If a pre-requisite is superseded by
another pre-requisite during the search, it is not considered a missing 
pre-requisite.

SMU name : pre-requisite 1, pre-requisite2, and etc..
"""
def get_missing_required_prerequisites(smu_loader, smu_info_list):
    all_required_prerequisite_set = set()
    missing_required_prerequisite_dict = {}
    smu_info_dict = get_dict_from_list(smu_info_list)
    
    for smu_info in smu_info_list:
        required_prerequisite_set = set()
        new_required_prerequisite_set = set()
        
        get_all_prerequisites(smu_loader, required_prerequisite_set, smu_info.name)
        
        for required_prerequisite in required_prerequisite_set:
            if required_prerequisite not in all_required_prerequisite_set:
                all_required_prerequisite_set.add(required_prerequisite)
        
        if len(required_prerequisite_set) > 0:
            for required_prerequisite in required_prerequisite_set:
                # If the pre-requisite is not already in the SMU list, proceed further
                if required_prerequisite not in smu_info_dict:
                    # Check if the missing pre-requisite has a SMU which
                    # supersedes it and is already in the SMU list.  If it is,
                    # it is not a missing pre-requisite.  The superseding SMU's
                    # pre-requisites should have already been included in
                    # getAllPreRequisites() above.
                    superseded_by_set = set()
                    get_all_superseded_bys(smu_loader, superseded_by_set, required_prerequisite)
                    
                    found = False
                    for superseded_by in superseded_by_set:
                        if superseded_by in smu_info_dict:
                            found = True
                            break
                            
                    if not found:
                        new_required_prerequisite_set.add(required_prerequisite)
                
            if len(new_required_prerequisite_set) > 0:
                missing_required_prerequisite_dict[smu_info.name] = new_required_prerequisite_set

    new_missing_required_prerequisite_dict = {}

    # Check to see if any pre-requisite is superseded by other pre-requisite
    for smu_name in missing_required_prerequisite_dict:
        new_missing_required_prerequisite_set = set()
        missing_required_prerequisite_set = missing_required_prerequisite_dict[smu_name]
        
        for missing_required_prerequisite in missing_required_prerequisite_set:
            if not is_superseded(smu_loader, all_required_prerequisite_set, missing_required_prerequisite):
                new_missing_required_prerequisite_set.add(missing_required_prerequisite)
        
        if len(new_missing_required_prerequisite_set) > 0:
            new_missing_required_prerequisite_dict [smu_name] = new_missing_required_prerequisite_set           
            
    return new_missing_required_prerequisite_dict  
 
"""
Given a SMU name, returns all its pre-requisites including its pre-requisites' pre-requisites.
SMU name can be SMU/SP name.
"""
def get_all_prerequisites(smu_loader, prerequisite_set, smu_name):
    smu_info = smu_loader.get_smu_info(smu_name)
    if smu_info is not None:
        prerequisites = comma_delimited_str_to_list(smu_info.prerequisites)
        if len(prerequisites) > 0:
            for prerequisite in prerequisites:
                if prerequisite not in prerequisite_set:
                    prerequisite_set.add(prerequisite)

                get_all_prerequisites(smu_loader, prerequisite_set, prerequisite)

"""
Given a SMU name, returns all the SMUs that supersede this SMU.
SMU name can be SMU/SP name.
"""                
def get_all_superseded_bys(smu_loader, superseded_by_set, smu_name):
    smu_info = smu_loader.get_smu_info(smu_name)
    if smu_info is not None:
        superseded_bys = comma_delimited_str_to_list(smu_info.superseded_by)    
        if len(superseded_bys) > 0:
            for superseded_by in superseded_bys:
                if superseded_by not in superseded_by_set:
                    superseded_by_set.add(superseded_by)
                    
                get_all_superseded_bys(smu_loader, superseded_by_set, superseded_by)

"""
Given a smu_name_set, check to see if the smu_name is tagged as a superseded SMU.  Each SMU
name in the smu_name_set represents a SMUInfo which may contain the smu_name as its supersedes.
"""                
def is_superseded(smu_loader, smu_name_list, smu_name):
    for name in smu_name_list:
        smu_info = smu_loader.get_smu_info(name)
        if smu_info is not None:
            superseded_smus = comma_delimited_str_to_list(smu_info.supersedes)
            for superseded_smu in superseded_smus:
                if superseded_smu == smu_name:
                    return True
            
    return False

"""
Given a smu_info_list, exclude SMUs that are superseded by other SMUs in the list.
"""
def get_excluded_supersede_list(smu_info_list):
    smu_info_dict = get_dict_from_list(smu_info_list)
    resultant_list = []
    
    for smu_info in smu_info_list:
        superseded_by_smus = comma_delimited_str_to_list(smu_info.superseded_by)
        is_superseded = False
        for superseded_by_smu in superseded_by_smus:
            if superseded_by_smu in smu_info_dict:
                is_superseded = True
                break
            
        if not is_superseded:
            resultant_list.append(smu_info)
            
    return resultant_list