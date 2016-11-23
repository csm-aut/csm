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
"""
SMUInfoLoader loads software information from XML files that are posted on CCO.
The XML files encode information for SMU, Service Pack, and Release Software for
a particular software platform and release.  If the requested XML file cannot be located,
it will attempt to load the information from the database.

The catalog file at this link contains all supported software platforms and releases
http://www.cisco.com/web/Cisco_IOS_XR_Software/SMUMetaFile/catalog.dat

Individual XML file can be retrieved using URL similar to the one below
http://www.cisco.com/web/Cisco_IOS_XR_Software/SMUMetaFile/asr9k_px_5.3.0.xml

Current defined software platforms are
asr9k_px
crs_px
ncs6k
ncs6k_sysadmin

The releases are expected to be in this format x.x.x (e.g. 5.3.0)
"""

from xml.dom import minidom

from sqlalchemy.exc import IntegrityError
from database import DBSession
from models import SMUMeta
from models import SMUInfo

from models import CCOCatalog
from models import logger
from models import SystemOption
from constants import UNKNOWN
from constants import PackageType
from constants import PlatformFamily

from smu_advisor import get_smus_exclude_supersedes_include_prerequisites
from collections import OrderedDict

import re
import requests
import datetime

CATALOG = 'catalog.dat'
IOSXR_URL = 'http://www.cisco.com/web/Cisco_IOS_XR_Software/SMUMetaFile'
URLS = [IOSXR_URL]

XML_TAG_PLATFORM = "platform"
XML_TAG_RELEASE = "release"
XML_TAG_CREATION_DATE = 'creationDate'
XML_TAG_SMU_SUFFIX = 'smuSuffix'
XML_TAG_PLATFORM_MDF_ID = "platformMDFID"
XML_TAG_PID = "pid"
XML_TAG_MDF_ID = "mdfID"
XML_TAG_SMU_SOFTWARE_TYPE_ID = 'smuSoftwareTypeID'
XML_TAG_SP_SOFTWARE_TYPE_ID = 'spSoftwareTypeID'
XML_TAG_TAR_SOFTWARE_TYPE_ID = 'tarSoftwareTypeID'
XML_TAG_ID = 'id'
XML_TAG_NAME = 'name'
XML_TAG_SMU_TYPE = 'smuType'
XML_TAG_SMU_CATEGORY = 'smuCategory'
XML_TAG_DESCRIPTION = 'description'
XML_TAG_IMPACT = 'impact'
XML_TAG_DDTS = 'ddts'
XML_TAG_POSTED = 'posted'
XML_TAG_SUPERCEDES = 'supercedes'
XML_TAG_SUPERCEDED_BY = 'supercededBy'
XML_TAG_PRE_REQUISITES = 'pre-requisites'
XML_TAG_PACKAGE_BUNDLES = 'packageBundles'
XML_TAG_FUNCTIONAL_AREAS = 'functionalAreas'
XML_TAG_POSTED_DATE = 'postedDate'
XML_TAG_ETA_DATE = 'customerETA'
XML_TAG_STATUS = 'status'
XML_TAG_COMPRESSED_IMAGE_SIZE = 'compressedImageSize'
XML_TAG_UNCOMPRESSED_IMAGE_SIZE = 'unCompressedImageSize'
XML_TAG_CCO_FILE_NAME = 'ccoFileName'
XML_TAG_COMPOSITE_DDTS = "compositeDDTS"  # Only SP has this attribute
XML_TAG_SMU = 'smu'
XML_TAG_SP = 'sp'
XML_TAG_SMU_INTRANSIT = 'smuIntransit'
XML_TAG_TAR = 'tar'

# These are the platform prefixes used by the XML files
# Any additions to this list will require modifying
# get_platform() and get_release()
CCO_PLATFORM_ASR9K = 'asr9k_px'
CCO_PLATFORM_CRS = 'crs_px'
CCO_PLATFORM_NCS6K = 'ncs6k'
CCO_PLATFORM_NCS6K_SYSADMIN = 'ncs6k_sysadmin'

class SMUInfoLoader(object):
    """
    Example: platform = asr9k_px, release = 4.2.1
    """
    def __init__(self, platform, release, refresh=False):
        self.platform = self.get_cco_supported_platform(platform)
        self.release = self.get_cco_supported_release(release)
        self.smu_meta = None
        self.smus = {}
        self.service_packs = {}
        self.in_transit_smus = {}
        self.software = {}

        if SystemOption.get(DBSession()).enable_cco_lookup or refresh:
            self.get_smu_info_from_cco(platform, release)
        else:
            self.get_smu_info_from_db(platform, release)

    def get_cco_supported_platform(self, platform):
        if platform == PlatformFamily.ASR9K:
            return CCO_PLATFORM_ASR9K
        elif platform == PlatformFamily.CRS:
            return CCO_PLATFORM_CRS
        elif platform == PlatformFamily.NCS6K:
            return CCO_PLATFORM_NCS6K
        else:
            return platform

    def get_cco_supported_release(self, release):
        matches = re.findall("\d+\.\d+\.\d+", release)
        if matches:
            return matches[0]
        return release
    
    def get_smu_info_from_db(self, platform, release):
        # self.smu_meta is set to None if the requested platform and release are not in the database.
        self.smu_meta = DBSession().query(SMUMeta).filter(SMUMeta.platform_release == platform + '_' + release).first()
        if not self.smu_meta is None:
            self.smus = self.get_smus_by_package_type(self.smu_meta.smu_info, PackageType.SMU)
            self.service_packs = self.get_smus_by_package_type(self.smu_meta.smu_info, PackageType.SERVICE_PACK)                
            self.in_transit_smus = self.get_smus_by_package_type(self.smu_meta.smu_info, PackageType.SMU_IN_TRANSIT)
            self.software = self.get_smus_by_package_type(self.smu_meta.smu_info, PackageType.SOFTWARE)
        
    def get_smu_info_from_cco(self, platform, release):
        same_as_db = False
        db_session = DBSession()
        platform_release = platform + '_' + release
        try:
            self.smu_meta = SMUMeta(platform_release=platform_release)
            # Load data from the SMU XML file
            self.load()

            # This can happen if the given platform and release is not valid.
            # The load method calls get_smu_info_from_db and failed.
            if self.smu_meta is None:
                return

            db_smu_meta = db_session.query(SMUMeta).filter(SMUMeta.platform_release == platform + '_' + release).first()
            if db_smu_meta is not None:               
                if db_smu_meta.created_time == self.smu_meta.created_time:
                    same_as_db = True
                else:
                    # Delete the existing smu_meta and smu_info for this platform and release
                    db_session.delete(db_smu_meta)
                    db_session.commit()

            if not same_as_db:
                db_session.add(self.smu_meta)
            else:
                db_smu_meta.retrieval_time = datetime.datetime.utcnow()

            # Use Flush to detect concurrent saving condition.  It is
            # possible that another process may perform the same save.
            # If this happens, Duplicate Key may result.
            db_session.flush()
            db_session.commit()

        except IntegrityError:
            db_session.rollback()
        except Exception:
            db_session.rollback()
            logger.exception('get_smu_info_from_cco() hit exception')
        
    def get_smus_by_package_type(self, smu_list, package_type):
        result_dict = {}
        
        for smu_info in self.smu_meta.smu_info:
            if smu_info.package_type == package_type:
                result_dict[smu_info.name] = smu_info
                
        return result_dict

    @property
    def is_valid(self):
        return True if self.smu_meta is not None else False

    @property
    def creation_date(self):
        return None if self.smu_meta is None else self.smu_meta.created_time
    
    @property
    def smu_software_type_id(self):
        return None if self.smu_meta is None else self.smu_meta.smu_software_type_id
    
    @property
    def sp_software_type_id(self):
        return None if self.smu_meta is None else self.smu_meta.sp_software_type_id

    @property
    def tar_software_type_id(self):
        return None if self.smu_meta is None else self.smu_meta.tar_software_type_id
    
    @property
    def pid(self):
        return None if self.smu_meta is None else self.smu_meta.pid
    
    @property
    def file_suffix(self):
        return None if self.smu_meta is None else self.smu_meta.file_suffix
    
    @property
    def mdf_id(self):
        return None if self.smu_meta is None else self.smu_meta.mdf_id
        
    def get_int_value(self, s):
        try:
            return int(s)
        except Exception:
            return 0

    def getChildElementText(self, parent_elem, child_name):
        try:
            return parent_elem.getElementsByTagName(child_name)[0].firstChild.data
        except Exception:
            return ''   
    
    def load_smu_info(self, node_list, smu_dict, package_type):
        for node in node_list:
            smu_info = SMUInfo(id=node.attributes[XML_TAG_ID].value)

            smu_info.name = self.getChildElementText(node, XML_TAG_NAME)
            smu_info.status = node.attributes[XML_TAG_STATUS].value
            smu_info.type = self.getChildElementText(node, XML_TAG_SMU_TYPE)
            smu_info.smu_category = self.getChildElementText(node, XML_TAG_SMU_CATEGORY)
            smu_info.posted_date = self.getChildElementText(node, XML_TAG_POSTED_DATE)
            smu_info.eta_date = self.getChildElementText(node, XML_TAG_ETA_DATE)
            smu_info.ddts = self.getChildElementText(node, XML_TAG_DDTS)
            smu_info.description = self.getChildElementText(node, XML_TAG_DESCRIPTION)
            smu_info.impact = self.getChildElementText(node, XML_TAG_IMPACT)
            smu_info.supersedes = self.getChildElementText(node, XML_TAG_SUPERCEDES)
            smu_info.superseded_by = self.getChildElementText(node, XML_TAG_SUPERCEDED_BY)
            smu_info.prerequisites = self.getChildElementText(node, XML_TAG_PRE_REQUISITES)
            smu_info.cco_filename = self.getChildElementText(node, XML_TAG_CCO_FILE_NAME)
            smu_info.functional_areas = self.getChildElementText(node, XML_TAG_FUNCTIONAL_AREAS)
            smu_info.package_bundles = self.getChildElementText(node, XML_TAG_PACKAGE_BUNDLES)
            smu_info.compressed_image_size = self.get_int_value(
                self.getChildElementText(node, XML_TAG_COMPRESSED_IMAGE_SIZE))
            smu_info.uncompressed_image_size = self.get_int_value(
                self.getChildElementText(node, XML_TAG_UNCOMPRESSED_IMAGE_SIZE))
            smu_info.composite_DDTS = self.getChildElementText(node, XML_TAG_COMPOSITE_DDTS)
            smu_info.package_type = package_type

            self.smu_meta.smu_info.append(smu_info)
            smu_dict[smu_info.name] = smu_info
            
        """
        for smu_name in smu_dict:
            smu_info = smu_dict[smu_name]
            prerequisite_smus = smu_info.prerequisites
            if len(prerequisite_smus) > 0:
                for prerequisite_smu in prerequisite_smus:
                    if prerequisite_smu in smu_dict:
                        prerequisite_smu_info = smu_dict[prerequisite_smu]
                        prerequisite_smu_info.prerequisite_to.append(smu_name)
        """

    def load(self):
        try:
            xmldoc = minidom.parseString(SMUInfoLoader.get_smu_meta_file(self.platform, self.release))
        except Exception:
            self.get_smu_info_from_db(self.platform, self.release)
            return

        # self._platform = self.getChildElementText(xmldoc, XML_TAG_PLATFORM)
        # self._release = self.getChildElementText(xmldoc, XML_TAG_RELEASE)
        self.smu_meta.retrieval_time = datetime.datetime.utcnow()
        self.smu_meta.created_time = self.getChildElementText(xmldoc, XML_TAG_CREATION_DATE)
        self.smu_meta.file_suffix = self.getChildElementText(xmldoc, XML_TAG_SMU_SUFFIX)
        self.smu_meta.smu_software_type_id = self.getChildElementText(xmldoc, XML_TAG_SMU_SOFTWARE_TYPE_ID)
        self.smu_meta.sp_software_type_id = self.getChildElementText(xmldoc, XML_TAG_SP_SOFTWARE_TYPE_ID)
        self.smu_meta.tar_software_type_id = self.getChildElementText(xmldoc, XML_TAG_TAR_SOFTWARE_TYPE_ID)
        
        node_list = xmldoc.getElementsByTagName(XML_TAG_PLATFORM_MDF_ID)
        if len(node_list) > 0:
            for node in node_list:
                self.smu_meta.pid = self.getChildElementText(node, XML_TAG_PID)
                self.smu_meta.mdf_id = self.getChildElementText(node, XML_TAG_MDF_ID)
                break
        
        # For SMUs that have been posted.
        self.load_smu_info(xmldoc.getElementsByTagName(XML_TAG_SMU), self.smus, PackageType.SMU)
        
        # For SMUs that have not been posted yet.
        self.load_smu_info(xmldoc.getElementsByTagName(XML_TAG_SMU_INTRANSIT),
                           self.in_transit_smus, PackageType.SMU_IN_TRANSIT)

        # For Service Packs that have been posted.
        self.load_smu_info(xmldoc.getElementsByTagName(XML_TAG_SP), self.service_packs, PackageType.SERVICE_PACK)

        # For Software Tar Files that have been posted.
        self.load_smu_info(xmldoc.getElementsByTagName(XML_TAG_TAR), self.software, PackageType.SOFTWARE)

    def get_smu_list(self):
        """
        Returns all the SMUs (posted and obsoleted).
        """
        return OrderedDict(sorted(self.smus.items())).values()
    
    def get_optimal_smu_list(self):
        return get_smus_exclude_supersedes_include_prerequisites(self, self.get_smu_list())

    def get_sp_list(self):
        """
        Returns all the Service Packs (posted and obsoleted).
        """
        return OrderedDict(sorted(self.service_packs.items())).values()
    
    def get_optimal_sp_list(self):
        return get_smus_exclude_supersedes_include_prerequisites(self, self.get_sp_list())

    def get_tar_list(self):
        return OrderedDict(sorted(self.software.items())).values()

    def get_smu_info(self, smu_name):
        """
        Given a SMU/SP name, returns the SMUInfo.
        """
        if smu_name in self.smus:
            return self.smus[smu_name]
        elif smu_name in self.in_transit_smus:
            return self.in_transit_smus[smu_name]
        elif smu_name in self.service_packs:
            return self.service_packs[smu_name]
        elif smu_name in self.software:
            return self.software[smu_name]
        else:
            return None
    
    def get_smu_info_by_id(self, smu_id):
        for smu in self.smus.values():
            if smu.id == smu_id:
                return smu
        for smu in self.in_transit_smus.values():
            if smu.id == smu_id:
                return smu
        for smu in self.service_packs.values():
            if smu.id == smu_id:
                return smu
        return None

    def get_ddts_from_names(self, name_list):
        """
        :param name_list: A list of SMU/SP names
        :return: An array of corresponding DDTS
        """
        results = []
        for name in name_list:
            smu_info = self.get_smu_info(name)
            if smu_info:
                results.append(smu_info.ddts)

        return results

    @classmethod   
    def get_smu_meta_file(cls, platform, release):
        try:
            url = IOSXR_URL + '/' + platform + '_' + release + '.xml'
            r = requests.get(url)
            return r.text
        except Exception:
            return None
    
    @classmethod
    def get_smu_meta_file_timestamp(cls, platform, release):
        try:
            url = IOSXR_URL + '/' + platform + '_' + release + '.lastPublishDate'

            r = requests.get(url)
            return r.text
        except Exception:
            return None
    
    @classmethod
    def get_catalog(cls):
        db_session = DBSession()        
        system_option = SystemOption.get(db_session)
        
        if system_option.enable_cco_lookup:
            return SMUInfoLoader.get_catalog_from_cco()
        else:
            catalog = {}
            # Retrieve from the database
            db_catalog = db_session.query(CCOCatalog).all()
            if len(db_catalog) > 0:
                for entry in db_catalog:
                    if entry.platform in catalog:
                        release_list = catalog[entry.platform]
                    else:
                        release_list = []
                        catalog[entry.platform] = release_list
                    
                    # Inserts release in reverse order (latest release first)
                    release_list.insert(0, entry.release)
                    
            return OrderedDict(sorted(catalog.items()))           

    @classmethod
    def get_catalog_from_cco(cls):
        """
        Returns a sorted dictionary representing the catalog.dat file.
            asr9k_px
                 4.2.3, 4.2.1
            crs_px
                4.3.0, 4.2.3, 4.2.1
            ncs6k
                5.0.1
            ncs6k_sysadmin
                5.0.1, 5.0.0
        """
        lines = []
        catalog = {}
    
        for url in URLS:
            try:
                r = requests.get(url + '/' + CATALOG)
                lines = r.text.splitlines()
            except Exception:
                pass
        
            for line in lines:
                # line should be in this format: asr9k_px_4.3.0
                # looks for the last underscore which is the delimiter
                last_pos = line.rfind('_')
                if last_pos > 0:
                    platform = line[:last_pos]
                    release = line[last_pos + 1:]
                 
                    if len(platform) > 0 and len(release) > 0:                    
                        if platform in catalog:
                            release_list = catalog[platform]
                        else:
                            release_list = []
                            catalog[platform] = release_list
                    
                        # Inserts release in reverse order (latest release first)
                        release_list.insert(0, release)

        return OrderedDict(sorted(catalog.items()))

    @classmethod
    def refresh_all(cls):
        """
        Retrieves all the catalog data and SMU XML file data and updates the database.
        """
        db_session = DBSession()
        
        catalog = SMUInfoLoader.get_catalog_from_cco()
        if len(catalog) > 0:
            system_option = SystemOption.get(db_session)
            try:
                # Remove all rows first
                db_session.query(CCOCatalog).delete()
            
                for platform in catalog:
                    releases = catalog[platform]
                    for release in releases:
                        cco_catalog = CCOCatalog(platform=platform,release=release)
                        db_session.add(cco_catalog)
                        
                        # Now, retrieve from SMU XML file
                        SMUInfoLoader(platform, release, refresh=True)
                
                system_option.cco_lookup_time = datetime.datetime.utcnow()
                db_session.commit()
                return True
            except Exception:
                logger.exception('refresh_all() hit exception')
                db_session.rollback()  
            
        return False

    @classmethod
    def get_cco_csm_messages(cls):
        """
        Returns an array of dictionary items { token : message }
        csmserver.msg file has token like
        @2015/5/1@Admin,Operator
          --- message ---
        @2015/4/1@Admin
          --- message ---
        """
        csm_messages = []
        message = ''
        date_token = None
        
        try:
            r = requests.get(URLS[0] + '/csmserver.msg')
            lines = r.text.splitlines()            
            for line in lines:    
                if len(line) > 0 and line[0] == '@':
                    if date_token is not None:
                        csm_messages.append({'token': date_token, 'message': message})
                    
                    date_token = line[1:]
                    message = ''
                elif date_token is not None:                    
                    message += line + "\n"
                    
        except Exception:
            pass
        
        if date_token is not None:
            csm_messages.append({'token': date_token, 'message': message})
        
        return csm_messages

    @classmethod
    def get_platform_and_release(cls, package_name):
        """
        Given a package_name, return the software platform and release that can be used to load an XML file.
        However, there is no guarantee that such XML exists.  Always call SMUInfoLoader.is_valid() to verify.

        'Unknown' may be returned for invalid platform or release.
        """
        package_list = None
        if isinstance(package_name, str):
            package_list = [package_name]
        elif isinstance(package_name, list):
            package_list = list(package_name)

        if package_list:
            for package_name in package_list:
                platform = UNKNOWN
                release = UNKNOWN

                if 'asr9k' in package_name and '-px' in package_name or 'ASR9K-iosxr' in package_name:
                    # Release Software Name: ASR9K-iosxr-px-k9-5.3.1.tar
                    # External Name: asr9k-mcast-px.pie-5.3.2 | asr9k-px-5.3.3.CSCuy81837.pie
                    # Internal Name: disk0:asr9k-mcast-px-5.3.2 | disk0:asr9k-px-5.3.3.CSCuy81837-1.0.0
                    platform = CCO_PLATFORM_ASR9K
                elif ('hfr' in package_name or 'CRS' in package_name) and '-px' in package_name:
                    # Release Software Name: CRS-iosxr-px-6.1.2.tar
                    # Internal Name: disk0:hfr-mini-px-4.2.1 | disk0:hfr-px-4.2.3.CSCtz89449
                    platform = CCO_PLATFORM_CRS
                elif 'ncs6k-sysadmin' in package_name:
                    # External Name: ncs6k-sysadmin.iso-5.2.4
                    # Internal Name: ncs6k-sysadmin-5.2.4
                    platform = CCO_PLATFORM_NCS6K_SYSADMIN
                elif 'ncs6k' in package_name:
                    # External Name: ncs6k-mgbl.pkg-5.2.4
                    # Internal Name: ncs6k-mgbl-5.2.4
                    platform = CCO_PLATFORM_NCS6K

                if platform in [CCO_PLATFORM_ASR9K, CCO_PLATFORM_CRS, CCO_PLATFORM_NCS6K, CCO_PLATFORM_NCS6K_SYSADMIN]:
                    matches = re.findall("\d+\.\d+\.\d+", package_name)
                    release = matches[0] if matches else UNKNOWN

                if platform != UNKNOWN and release != UNKNOWN:
                    return platform, release

        return UNKNOWN, UNKNOWN

if __name__ == '__main__':
    SMUInfoLoader.refresh_all()

