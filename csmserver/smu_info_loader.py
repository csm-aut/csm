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
from sqlalchemy import and_

from xml.dom import minidom

from database import DBSession

from models import SMUMeta
from models import SMUInfo
from models import logger
from models import SystemOption
from models import PackageToSMU

from constants import UNKNOWN
from constants import PackageType
from constants import PlatformFamily

from utils import is_empty

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
XML_TAG_PACKAGE_NAMES = 'packageNames'
XML_TAG_PACKAGE_MD5 = 'packageMD5'

XML_TAG_SMU = 'smu'
XML_TAG_SP = 'sp'
XML_TAG_SMU_INTRANSIT = 'smuIntransit'
XML_TAG_TAR = 'tar'

# These are the platform prefixes used by the XML files
# Any additions to this list will require modifying
# get_cco_supported_platform() and get_cco_supported_release()
CCO_PLATFORM_ASR9K = 'asr9k_px'
CCO_PLATFORM_ASR9K_X64 = 'asr9k_x64'
CCO_PLATFORM_XRV9K = 'xrv9k'
CCO_PLATFORM_CRS = 'crs_px'
CCO_PLATFORM_NCS1K = 'ncs1k'
CCO_PLATFORM_NCS4K = 'ncs4k'
CCO_PLATFORM_NCS5K = 'ncs5k'
CCO_PLATFORM_NCS5500 = 'ncs5500'
CCO_PLATFORM_NCS6K = 'ncs6k'

CCO_PLATFORM_XRV9K_SYSADMIN = 'xrv9k_sysadmin'
CCO_PLATFORM_NCS1K_SYSADMIN = 'ncs1k_sysadmin'
CCO_PLATFORM_NCS4K_SYSADMIN = 'ncs4k_sysadmin'
CCO_PLATFORM_NCS5K_SYSADMIN = 'ncs5k_sysadmin'
CCO_PLATFORM_NCS5500_SYSADMIN = 'ncs5500_sysadmin'
CCO_PLATFORM_NCS6K_SYSADMIN = 'ncs6k_sysadmin'
CCO_PLATFORM_ASR9K_X64_SYSADMIN = 'asr9k_x64_sysadmin'


class SMUInfoLoader(object):
    """
    Example: platform = asr9k_px, release = 4.2.1
    """
    def __init__(self, platform, release, from_cco=True):
        self.platform = self.get_cco_supported_platform(platform)
        self.release = self.get_cco_supported_release(release)

        self.smu_meta = None
        self.smus = {}
        self.service_packs = {}
        self.in_transit_smus = {}
        self.software = {}

        if not SystemOption.get(DBSession()).enable_cco_lookup:
            from_cco = False

        if self.platform != UNKNOWN and self.release != UNKNOWN:
            if from_cco:
                self.get_smu_info_from_cco(self.platform, self.release)
            else:
                self.get_smu_info_from_db(self.platform, self.release)

    def get_cco_supported_platform(self, platform):
        if platform == PlatformFamily.ASR9K:
            return CCO_PLATFORM_ASR9K
        elif platform == PlatformFamily.ASR9K_X64:
            return CCO_PLATFORM_ASR9K_X64
        elif platform == PlatformFamily.CRS:
            return CCO_PLATFORM_CRS
        elif platform == PlatformFamily.NCS4K:
            return CCO_PLATFORM_NCS4K
        elif platform == PlatformFamily.NCS5K:
            return CCO_PLATFORM_NCS5K
        elif platform == PlatformFamily.NCS5500:
            return CCO_PLATFORM_NCS5500
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
        self.smu_meta = DBSession().query(SMUMeta).filter(and_(SMUMeta.platform == platform,
                                                               SMUMeta.release == release)).first()
        if self.smu_meta:
            for smu_info in self.smu_meta.smu_info:
                if smu_info.package_type == PackageType.SMU:
                    self.smus[smu_info.name] = smu_info
                elif smu_info.package_type == PackageType.SERVICE_PACK:
                    self.service_packs[smu_info.name] = smu_info
                elif smu_info.package_type == PackageType.SMU_IN_TRANSIT:
                    self.in_transit_smus[smu_info.name] = smu_info
                elif smu_info.package_type == PackageType.SOFTWARE:
                    self.software[smu_info.name] = smu_info

    def get_smu_info_from_cco(self, platform, release):
        save_to_db = True
        db_session = DBSession()

        try:
            self.smu_meta = SMUMeta(platform=platform, release=release)
            # Load data from the SMU XML file
            self.load()

            # This can happen if the given platform and release is not valid.
            # The load() method calls get_smu_info_from_db and failed.
            if not self.is_valid:
                logger.error('get_smu_info_from_cco() hit error platform={}, release={}'.format(platform, release))
                return

            db_smu_meta = db_session.query(SMUMeta).filter(and_(SMUMeta.platform == platform,
                                                                SMUMeta.release == release)).first()
            if db_smu_meta:
                if db_smu_meta.created_time == self.smu_meta.created_time:
                    save_to_db = False
                else:
                    # Delete the existing smu_meta and smu_info for this platform and release
                    db_session.delete(db_smu_meta)
                    db_session.commit()

            if save_to_db:
                db_session.add(self.smu_meta)
                self.create_package_to_smu_xref(db_session)
            else:
                db_smu_meta.retrieval_time = datetime.datetime.utcnow()

            db_session.commit()

        except Exception:
            logger.exception('get_smu_info_from_cco() hit exception platform={}, release={}'.format(platform, release))

    def create_package_to_smu_xref(self, db_session):
        for smu_info in self.smu_meta.smu_info:
            if not is_empty(smu_info.package_names):
                for package_name in smu_info.package_names.split(','):
                    package_to_smu = SMUInfoLoader.get_package_smu_from_package_name(db_session, package_name)
                    if package_to_smu is None:
                        db_session.add(PackageToSMU(package_name=package_name, smu_name=smu_info.name))
                    else:
                        if package_to_smu.smu_name != smu_info.name:
                            package_to_smu.smu_name = smu_info.name

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
            smu_info.package_names = self.getChildElementText(node, XML_TAG_PACKAGE_NAMES)
            smu_info.package_md5 = self.getChildElementText(node, XML_TAG_PACKAGE_MD5)

            # For Release Software tar file, use the smu name.
            if package_type == PackageType.SOFTWARE:
                smu_info.package_names = smu_info.name

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
    def get_package_names_from_smu_name(cls, db_session, smu_name):
        """
        For eXR platforms which are using RPM.  It is possible that a SMU may contain multiple RPM images.
        This information is store in a xref table called ImageToSMU.
        """
        return db_session.query(PackageToSMU.package_name).filter(PackageToSMU.smu_name == smu_name).all()

    @classmethod
    def get_smu_name_from_package_name(cls, db_session, package_name):
        package_to_smu = SMUInfoLoader.get_package_smu_from_package_name(db_session, package_name)
        return None if package_to_smu is None else package_to_smu.smu_name

    @classmethod
    def get_package_smu_from_package_name(cls, db_session, package_name):
        return db_session.query(PackageToSMU).filter(PackageToSMU.package_name == package_name).first()

    @classmethod
    def get_cco_file_package_type(cls, db_session, name):
        """
        :param name: name can be a package name or cco file name
        :return: returns the package type of the cco file
        """
        smu_info = db_session.query(SMUInfo).filter(SMUInfo._cco_filename == name).first()
        if smu_info:
            return smu_info.package_type

        return UNKNOWN

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
            catalog_entries = db_session.query(SMUMeta).all()
            if len(catalog_entries) > 0:
                for entry in catalog_entries:
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
                for platform, releases in catalog.iteritems():
                    for release in releases:
                        SMUInfoLoader(platform, release)
                
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
    def get_release_from_rxxx(cls, package_name):
        """ Return the release as x.x.x given a package_name with release informaton in '-rxxx' format """
        matches = re.findall("-r(\d{3})", package_name)
        if matches:
            return ".".join(matches[0])
        return UNKNOWN

    @classmethod
    def get_loader_from_package(cls, package_name):
        platform, release = SMUInfoLoader.get_platform_and_release(package_name)
        return SMUInfoLoader(platform, release)

    @classmethod
    def get_platform_and_release(cls, package_name):
        """
        Given a package_name, return the software platform and release that can be used to load an XML file.
        However, there is no guarantee that such XML exists.  Always call SMUInfoLoader.is_valid() to verify.

        'Unknown' may be returned for invalid platform or release.
        """
        if isinstance(package_name, list):
            package_list = list(package_name)
        else:
            package_list = [package_name]

        for package_name in package_list:
            platform = UNKNOWN
            release = UNKNOWN

            if 'asr9k' in package_name and '-px' in package_name or 'ASR9K-iosxr' in package_name:
                # Release Software Name: ASR9K-iosxr-px-k9-5.3.1.tar
                # External Name: asr9k-mcast-px.pie-5.3.2 | asr9k-px-5.3.3.CSCuy81837.pie
                # Internal Name: disk0:asr9k-mcast-px-5.3.2 | disk0:asr9k-px-5.3.3.CSCuy81837-1.0.0
                platform = CCO_PLATFORM_ASR9K

            # FIXME:
            # Some of the inconsistencies CSM needs to deal with
            # iosxr-os-asr9k-64-5.0.0.1-r613.CSCvc01618.x86_64.rpm
            # ASR9K-x64-iosxr-px-6.2.2.tar
            # asr9k-mini-x64-migrate_to_eXR.tar-6.2.2
            # The argument to this function should probably use the SMU name which has standard format
            elif any(s in package_name for s in ['ASR9K', 'asr9k']) and \
                 any(s in package_name for s in ['x64', '64']):

                # External Name: asr9k-mgbl-x64-3.0.0.0-r612.x86_64.rpm, asr9k-mini-x64-6.2.1.iso
                # Internal Name: asr9k-mgbl-x64-3.0.0.0-r612, asr9k-mini-x64-6.3.1
                platform = CCO_PLATFORM_ASR9K_X64
                if "mini" not in package_name:
                    release = SMUInfoLoader.get_release_from_rxxx(package_name)

            elif any(s in package_name for s in ['asr9k-sysadmin', 'asr9k-xr']):

                # External Name:
                # Internal Name: asr9k-sysadmin-6.2.1, asr9k-xr-6.2.1
                platform = CCO_PLATFORM_ASR9K_X64_SYSADMIN

            elif 'xrv9k' in package_name:

                if any(s in package_name for s in ['xrv9k-sysadmin', 'xvr9k-xr']):
                    # External Name:
                    # Internal Name: xrv9k-sysadmin-6.1.1, xrv9k-xr-6.1.1
                    platform = CCO_PLATFORM_XRV9K_SYSADMIN
                else:
                    # External Name: xrv9k-k9sec-3.0.0.1-r611.CSCvd41122.x86_64.rpm, xrv9k-mini-x-6.1.2.iso
                    # Internal Name: ?, xrv9k-mini-x-6.1.2
                    platform = CCO_PLATFORM_XRV9K
                    if "mini" not in package_name:
                        release = SMUInfoLoader.get_release_from_rxxx(package_name)

            elif ('hfr' in package_name or 'CRS' in package_name) and '-px' in package_name:

                # Release Software Name: CRS-iosxr-px-6.1.2.tar
                # Internal Name: disk0:hfr-mini-px-4.2.1 | disk0:hfr-px-4.2.3.CSCtz89449
                platform = CCO_PLATFORM_CRS

            elif 'ncs1k' in package_name:

                if any(s in package_name for s in ['ncs1k-sysadmin', 'ncs1k-xr']):
                    # External Name:
                    # Internal Name: ncs1k-sysadmin-6.3.1, ncs1k-xr-6.3.1
                    platform = CCO_PLATFORM_NCS1K_SYSADMIN
                else:
                    # External Name: ncs1k-mgbl.pkg-6.1.3
                    # Internal Name: ncs1k-k9sec-3.1.0.0-r631, ncs1k-os-support-3.0.0.2-r631.CSCve05411
                    platform = CCO_PLATFORM_NCS1K
                    release = SMUInfoLoader.get_release_from_rxxx(package_name)

            elif 'ncs4k' in package_name:

                if any(s in package_name for s in ['ncs4k-sysadmin', 'ncs4k-xr']):
                    # External Name:
                    # Internal Name: ncs4k-sysadmin-6.1.12
                    platform = CCO_PLATFORM_NCS4K_SYSADMIN
                else:
                    # External Name: ncs4k-mgbl.pkg-6.1.2
                    # Internal Name: ncs4k-mgbl-6.1.2
                    platform = CCO_PLATFORM_NCS4K

            elif 'ncs5k' in package_name:

                if any(s in package_name for s in ['ncs5k-sysadmin', 'ncs5k-xr']):
                    # External Name:
                    # Internal Name: ncs5k-sysadmin-6.1.2, ncs5k-xr-6.1.2
                    platform = CCO_PLATFORM_NCS5K_SYSADMIN
                else:
                    # External Name: ncs5k-mgbl-3.0.0.0-r612.x86_64.rpm, ncs5k-6.0.1.CSCva07993.rpm
                    # Internal Name: ncs5k-mgbl-3.0.0.0-r612
                    platform = CCO_PLATFORM_NCS5K
                    release = SMUInfoLoader.get_release_from_rxxx(package_name)

            elif 'ncs5500' in package_name:

                if any(s in package_name for s in ['ncs5500-sysadmin', 'ncs5500-xr']):
                    # External Name:
                    # Internal Name: ncs5500-sysadmin-6.1.2, ncs5500-xr-6.1.2
                    platform = CCO_PLATFORM_NCS5500_SYSADMIN
                else:
                    # External Name: ncs5500-mgbl-3.0.0.0-r612.x86_64.rpm
                    # Internal Name: ncs5500-mgbl-3.0.0.0-r612
                    platform = CCO_PLATFORM_NCS5500
                    release = SMUInfoLoader.get_release_from_rxxx(package_name)

            elif 'ncs6k' in package_name:

                if any(s in package_name for s in ['ncs6k-sysadmin', 'ncs6k-xr']):
                    # External Name: ncs6k-sysadmin.iso-5.2.4
                    # Internal Name: ncs6k-sysadmin-5.2.4, ncs6k-xr-5.2.4
                    platform = CCO_PLATFORM_NCS6K_SYSADMIN
                else:
                    # External Name: ncs6k-mgbl.pkg-5.2.4
                    # Internal Name: ncs6k-mgbl-5.2.4
                    platform = CCO_PLATFORM_NCS6K

            if release == UNKNOWN and platform in [CCO_PLATFORM_ASR9K,
                                                   CCO_PLATFORM_ASR9K_X64,
                                                   CCO_PLATFORM_ASR9K_X64_SYSADMIN,
                                                   CCO_PLATFORM_XRV9K,
                                                   CCO_PLATFORM_XRV9K_SYSADMIN,
                                                   CCO_PLATFORM_CRS,
                                                   CCO_PLATFORM_NCS1K,
                                                   CCO_PLATFORM_NCS1K_SYSADMIN,
                                                   CCO_PLATFORM_NCS4K,
                                                   CCO_PLATFORM_NCS4K_SYSADMIN,
                                                   CCO_PLATFORM_NCS5K,
                                                   CCO_PLATFORM_NCS5K_SYSADMIN,
                                                   CCO_PLATFORM_NCS5500,
                                                   CCO_PLATFORM_NCS5500_SYSADMIN,
                                                   CCO_PLATFORM_NCS6K,
                                                   CCO_PLATFORM_NCS6K_SYSADMIN]:

                    matches = re.findall("\d+\.\d+\.\d+", package_name)
                    release = matches[0] if matches else UNKNOWN

            if platform != UNKNOWN and release != UNKNOWN:
                return platform, release

        return UNKNOWN, UNKNOWN

if __name__ == '__main__':
    SMUInfoLoader.refresh_all()

