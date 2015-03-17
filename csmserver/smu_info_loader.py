from xml.dom import minidom

from sqlalchemy.exc import IntegrityError
from database import DBSession
from models import SMUMeta
from models import SMUInfo
from constants import PackageType

from smu_advisor import get_smus_exclude_supersedes_include_prerequisites
from collections import OrderedDict

import requests
import time

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
XML_TAG_ID = 'id'
XML_TAG_SMU = 'smu'
XML_TAG_NAME = 'name'
XML_TAG_SMU_TYPE = 'smuType'
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
XML_TAG_COMPOSITE_DDTS = "compositeDDTS";  # Only SP has this attribute
XML_TAG_SMU = 'smu'
XML_TAG_SP = 'sp'
XML_TAG_SMU_INTRANSIT = 'smuIntransit'

class SMUInfoLoader(object):
    """
    Example: platform = asr9k_px, release = 4.2.1
    """
    def __init__(self, platform, release):
        self.platform = platform
        self.release = release
        self.smu_meta = None
        self.smus = {}
        self.service_packs = {}
        self.in_transit_smus = {}
        
        db_session = DBSession()
        self.smu_meta = db_session.query(SMUMeta).filter(SMUMeta.platform_release == platform + '_' + release).first()
        if self.smu_meta == None:  
            self.get_smu_info_from_cco(db_session, platform + '_' + release)  
        else:
            downloaded_date = self.smu_meta.downloaded_time.split()[0]
            current_date = time.strftime('%m/%d/%Y')
            
            if downloaded_date != current_date:
                db_session.delete(self.smu_meta)
                self.get_smu_info_from_cco(db_session, platform + '_' + release)  
            else:
                self.smus = self.get_smus_by_package_type(self.smu_meta.smu_info, PackageType.SMU)
                self.service_packs = self.get_smus_by_package_type(self.smu_meta.smu_info, PackageType.SERVICE_PACK)
                self.in_transit_smus = self.get_smus_by_package_type(self.smu_meta.smu_info, PackageType.SMU_IN_TRANSIT)
   
    def get_smu_info_from_cco(self, db_session, platform_release):
       
        try:
            self.smu_meta = SMUMeta(platform_release=platform_release)
            # Load the data
            self.load()
            
            db_session.add(self.smu_meta)
            # Use Flush to detect concurrent saving condition.  It is
            # possible that another process may perform the same save.
            # If this happens, Duplicate Key may result.
            db_session.flush()
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
        
    def get_smus_by_package_type(self, smu_list, package_type):
        result_dict = {}
        
        for smu_info in self.smu_meta.smu_info:
            if smu_info.package_type == package_type:
                result_dict[smu_info.name] = smu_info
                
        return result_dict
    
    @property
    def creation_date(self):
        return self.smu_meta.created_time
    
    @property
    def smu_software_type_id(self):
        return self.smu_meta.smu_software_type_id
    
    @property
    def sp_software_type_id(self):
        return self.smu_meta.sp_software_type_id
    
    @property
    def pid(self):
        return self.smu_meta.pid
    
    @property
    def file_suffix(self):
        return self.smu_meta.file_suffix
    
    @property
    def mdf_id(self):
        return self.smu_meta.mdf_id
        
    def get_int_value(self, s):
        try:
            return int(s)
        except:
            return 0
        
    def getChildElementText(self, parent_elem, child_name):
        try:
            return parent_elem.getElementsByTagName(child_name)[0].firstChild.data
        except:
            return ''   
    
    def load_smu_info(self, node_list, smu_dict, package_type):
        for node in node_list:
            smu_info = SMUInfo(id=node.attributes[XML_TAG_ID].value)
            
            smu_info.status = node.attributes[XML_TAG_STATUS].value       
            smu_info.name = self.getChildElementText(node, XML_TAG_NAME)
            
            smu_info.type = self.getChildElementText(node, XML_TAG_SMU_TYPE)
            smu_info.posted_date = self.getChildElementText(node, XML_TAG_POSTED_DATE)
            smu_info.eta_date = self.getChildElementText(node, XML_TAG_ETA_DATE)
            smu_info.ddts = self.getChildElementText(node, XML_TAG_DDTS)
            smu_info.description = self.getChildElementText(node, XML_TAG_DESCRIPTION) 
            smu_info.impact = self.getChildElementText(node, XML_TAG_IMPACT) 
            smu_info.cco_filename = self.getChildElementText(node, XML_TAG_CCO_FILE_NAME)
   
            smu_info.supersedes = self.getChildElementText(node, XML_TAG_SUPERCEDES)
            smu_info.superseded_by = self.getChildElementText(node, XML_TAG_SUPERCEDED_BY)
            smu_info.prerequisites = self.getChildElementText(node, XML_TAG_PRE_REQUISITES)
            smu_info.functional_areas = self.getChildElementText(node, XML_TAG_FUNCTIONAL_AREAS)               
            smu_info.package_bundles = self.getChildElementText(node, XML_TAG_PACKAGE_BUNDLES)
            smu_info.compressed_image_size = self.get_int_value(self.getChildElementText(node, XML_TAG_COMPRESSED_IMAGE_SIZE))              
            smu_info.uncompressed_image_size = self.get_int_value(self.getChildElementText(node, XML_TAG_UNCOMPRESSED_IMAGE_SIZE))
            smu_info.composite_DDTS = self.getChildElementText(node, XML_TAG_COMPOSITE_DDTS);
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
        xmldoc = minidom.parseString(SMUInfoLoader.get_smu_meta_file(self.platform, self.release))
        
        # self._platform = self.getChildElementText(xmldoc, XML_TAG_PLATFORM)
        # self._release = self.getChildElementText(xmldoc, XML_TAG_RELEASE)
        self.smu_meta.downloaded_time = time.strftime('%m/%d/%Y %I:%M:%S %p')
        self.smu_meta.created_time = self.getChildElementText(xmldoc, XML_TAG_CREATION_DATE)
        self.smu_meta.file_suffix = self.getChildElementText(xmldoc, XML_TAG_SMU_SUFFIX)
        self.smu_meta.smu_software_type_id = self.getChildElementText(xmldoc, XML_TAG_SMU_SOFTWARE_TYPE_ID)
        self.smu_meta.sp_software_type_id = self.getChildElementText(xmldoc, XML_TAG_SP_SOFTWARE_TYPE_ID)
        
        node_list = xmldoc.getElementsByTagName(XML_TAG_PLATFORM_MDF_ID)
        if len(node_list) > 0:
            for node in node_list:
                self.smu_meta.pid = self.getChildElementText(node, XML_TAG_PID)
                self.smu_meta.mdf_id = self.getChildElementText(node, XML_TAG_MDF_ID)
                break
        
        # For SMUs that have been posted.
        self.load_smu_info(xmldoc.getElementsByTagName(XML_TAG_SMU), self.smus, PackageType.SMU)
        
        # For SMUs that have not been posted yet.
        self.load_smu_info(xmldoc.getElementsByTagName(XML_TAG_SMU_INTRANSIT), self.in_transit_smus, PackageType.SMU_IN_TRANSIT);
        
        # For Service Packs that have been posted.
        self.load_smu_info(xmldoc.getElementsByTagName(XML_TAG_SP), self.service_packs, PackageType.SERVICE_PACK);
        
    """
    Returns all the SMUs (posted and obsoleted).
    """
    def get_smu_list(self):
        return OrderedDict(sorted(self.smus.items())).values()
    
    def get_optimal_smu_list(self):
        return get_smus_exclude_supersedes_include_prerequisites(self, self.get_smu_list())
    """
    Returns all the Service Packs (posted and obsoleted).
    """
    def get_sp_list(self):
        return OrderedDict(sorted(self.service_packs.items())).values()
    
    def get_optimal_sp_list(self):
        return get_smus_exclude_supersedes_include_prerequisites(self, self.get_sp_list())
    
    """
    Given a SMU/SP name, returns the SMUInfo.
    """
    def get_smu_info(self, smu_name):
        if smu_name in self.smus:
            return self.smus[smu_name]
        elif smu_name in self.in_transit_smus:
            return self.in_transit_smus[smu_name]
        elif smu_name in self.service_packs:
            return self.service_packs[smu_name]
        else:
            return None
    
    @classmethod   
    def get_smu_meta_file(cls, platform, release):
        try:
            url = IOSXR_URL + '/' + platform + '_' + release + '.xml'
            r = requests.get(url)
            return r.text
        except:
            return None
    
    @classmethod
    def get_smu_meta_file_timestamp(cls, platform, release):
        try:
            url = IOSXR_URL + '/' + platform + '_' + release + '.lastPublishDate'
            r = requests.get(url)
            return r.text
        except:
            return None
    
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
    @classmethod
    def get_catalog(cls):
        lines = []
        catalog = {}
    
        for url in URLS:
            try:
                r = requests.get(url + '/' + CATALOG)
                lines = r.text.splitlines()
            except:
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


if __name__ == '__main__':
    smu_loader = SMUInfoLoader('asr9k_px', '4.2.1')

