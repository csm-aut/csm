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
from database import DBSession

from constants import UNKNOWN
from constants import PackageType

from smu_info_loader import SMUInfoLoader

from smu_advisor import get_excluded_supersede_list 
from smu_advisor import get_missing_required_prerequisites
from smu_advisor import get_dict_from_list

from utils import multiple_replace

SMU_INDICATOR = 'CSC'
SP_INDICATOR = '.sp'
TAR_INDICATOR = 'iosxr'
    

def get_package_type(name):
    """
    Returns the package type.  Available package types are defined in PackageType.

    Only ASR9K supports Service Packs concept
    Example: asr9k-px-4.3.2.sp-1.0.0 or asr9k-px-4.3.2.k9-sp-1.0.0
    """
    if name.find(SMU_INDICATOR) != -1:
        return PackageType.SMU
    elif name.find(SP_INDICATOR) != -1:
        return PackageType.SERVICE_PACK
    elif name.find(TAR_INDICATOR) != -1:
        return PackageType.SOFTWARE
    else:
        return PackageType.PACKAGE
    

def get_smu_lookup_name(name):
    """
    Given a package name, try to derive a name which can be used to lookup a SMU or SP
    in the SMU meta file.

    However, there is no guarantee that the correct name can be derived. That depends
    on the given name if it is within the parsing criteria.
    """
    name = name.strip()
    package_type = get_package_type(name)
    if package_type != PackageType.SMU and package_type != PackageType.SERVICE_PACK:
        return name
    
    # The worst case scenario of the name could be "disk0:asr9k-px-4.2.1.CSCud90009-1.0.0.pie"
    # .smu is for NCS6K, .rpm is for ASR9K-X64
    rep_dict = {'.pie': '', '.smu': '', '.rpm': ''}
    name = multiple_replace(name, rep_dict)
    
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


def union_set_from_dict(smu_info_dict):
    """
    The smu_info_dict has the following format
       smu name ->  set()
    """
    result_set = set()
    for smu_set in smu_info_dict.values():
        result_set = result_set.union(smu_set)
            
    return result_set


def get_missing_prerequisite_list(smu_loader, smu_name_list):
    """
    :param smu_loader: A valid SMUInfoLoader instance
    :param smu_name_list: A list of SMU names.  For example,
                                 asr9k-px-6.1.3.CSCvd54775
                                 ncs5500-6.1.3.CSCvd07722
    :return: Returns a list SMU names that are the missing pre-requisites if any.
    """
    result_list = []

    if smu_loader.is_valid:
        smu_info_dict = dict()

        for smu_name in smu_name_list:
            smu_info = smu_loader.get_smu_info(smu_name)

            if smu_info is not None:
                smu_info_dict[smu_name] = smu_info

        if len(smu_info_dict) > 0:
            # Exclude all the superseded SMUs in smu_info_list
            excluded_supersede_list = get_excluded_supersede_list(smu_info_dict.values())

            missing_required_prerequisite_dict = \
                get_missing_required_prerequisites(smu_loader, excluded_supersede_list)

            missing_required_prerequisite_set = union_set_from_dict(missing_required_prerequisite_dict)
            for pre_requisite_smu in missing_required_prerequisite_set:
                result_list.append(pre_requisite_smu)
                
    return result_list


def get_peer_packages(db_session, smu_loader, package_name):
    """
    On eXR platforms, a SMU may contain multiple RPMs.  Not only does CSM need
    to check for missing pre-requisite, but also missing peers in the same SMU.
    :param db_session: A DBSession instance
    :param smu_loader: A SMUInfoLoader instance
    :param package_name: A package name
    :return: Returns the peer packages
    """
    smu_name = SMUInfoLoader.get_smu_name_from_package_name(db_session, package_name=package_name)
    smu_info = smu_loader.get_smu_info(smu_name)
    if smu_info is not None:
        return smu_info.package_names.split(',')
    return []


def get_smu_info_dict(db_session, smu_loader, package_list):
    """
    Given a package list, return a dictionary.  If a package name cannot be resolved to a SMU name, its value will be None.
    :param db_session: A DBSession instance
    :param smu_loader: A SMUInfoLoader instance
    :param package_list: A list of package names
              asr9k-px-6.1.3.CSCvd54775.pie
              ncs5500-k9sec-2.2.0.2-r613.CSCvd18741.x86_64.rpm
    :return: A dictionary
        key: package_name, value: SMUInfo
    """
    smu_info_dict = dict()

    for package_name in package_list:
        smu_name = SMUInfoLoader.get_smu_name_from_package_name(db_session, package_name=package_name)
        smu_info_dict[package_name] = smu_loader.get_smu_info(smu_name)

    return smu_info_dict


def get_optimized_list(package_to_optimize_list):
    """
    Returns the validated list given the SMU/SP list.
    A smu_list may contain packages, SMUs, SPs, or junk texts.
    """
    unrecognized_list = []
    package_list = []
    result_list = []
    db_session = DBSession()
    missing_peer_packages_dict = dict()

    smu_loader = SMUInfoLoader.get_loader_from_package(package_to_optimize_list)
    if smu_loader.is_valid:
        smu_info_list = []
        smu_info_dict = get_smu_info_dict(DBSession(), smu_loader, package_to_optimize_list)

        for package_name, smu_info in smu_info_dict.items():
            if smu_info is None:
                # Check if the entry is a package type
                platform, release = SMUInfoLoader.get_platform_and_release(package_name)
                if platform == UNKNOWN:
                    unrecognized_list.append(package_name)
                else:
                    package_list.append(package_name)
            else:
                smu_info_list.append(smu_info)

        if len(smu_info_list) > 0:
            # Exclude all the superseded SMUs in smu_info_list
            excluded_supersede_list = get_excluded_supersede_list(smu_info_list)
            missing_required_prerequisite_dict = \
                get_missing_required_prerequisites(smu_loader, excluded_supersede_list)

            missing_required_prerequisite_set = union_set_from_dict(missing_required_prerequisite_dict)
            for pre_requisite_smu in missing_required_prerequisite_set:
                pre_requisite_smu_info = smu_loader.get_smu_info(pre_requisite_smu)
                description = pre_requisite_smu_info.description if pre_requisite_smu_info is not None else ''

                for package_name in pre_requisite_smu_info.package_names.split(','):
                    result_list.append({'smu_entry': package_name,
                                        'is': 'Pre-requisite', 'description': description})

            excluded_supersede_dict = get_dict_from_list(excluded_supersede_list)

            for smu_info in smu_info_list:
                if smu_info.name not in excluded_supersede_dict:
                    for package_name in smu_info.package_names.split(','):
                        result_list.append({'smu_entry': package_name,
                                            'is': 'Superseded', 'description': smu_info.description})
                else:
                    for package_name in smu_info.package_names.split(','):
                        result_list.append({'smu_entry': package_name,
                                            'is': 'SMU/SP', 'description': smu_info.description})

        if len(package_list) > 0:
            for package_name in package_list:
                result_list.append({'smu_entry': package_name, 'is': 'Package', 'description': ''})

        if len(unrecognized_list) > 0:
            for package_name in unrecognized_list:
                result_list.append({'smu_entry': package_name, 'is': 'Unrecognized', 'description': ''})

    else:
        for package_name in package_to_optimize_list:
            result_list.append({'smu_entry': package_name, 'is': 'Unrecognized', 'description': ''})

    return result_list

if __name__ == '__main__':
    pass