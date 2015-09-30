import xlwt

from filters import get_datetime_string
from smu_utils import get_platform_and_release
from platform_matcher import UNKNOWN
from smu_info_loader import SMUInfoLoader
from constants import JobStatus

class XLSWriter(object):   
        
    style_title = xlwt.easyxf('font: height 350, bold on; align: vert centre, horiz center;')
    style_bold = xlwt.easyxf('font: bold on, height 260;')
    style_summary = xlwt.easyxf('font: height 220;')
    style_center = xlwt.easyxf('align: vert centre, horiz center;')

    def __init__(self, conformance_report, filename, locale_datetime=None, include_host_packages=True):
        self.row = 0       
        self.filename = filename
        self.conformance_report = conformance_report
        self.locale_datetime = locale_datetime
        self.include_host_packages = include_host_packages
    
    def write_report(self):
        self.init_report()
        self.write_header_info()
        
        self.row = 12
        self.write_software_profile_info()
        self.write_host_info()
        
        self.wb.save(self.filename)    
     
    def init_report(self):
        self.wb = xlwt.Workbook()
        self.ws = self.wb.add_sheet('Conformance Report')
        self.ws.set_portrait(False)
        
        self.ws.col(0).width = 7000
        self.ws.col(1).width = 5000
        self.ws.col(2).width = 8000
        self.ws.col(3).width = 8000
        self.ws.col(4).width = 5000
        
    def write_header_info(self):
        self.ws.write(0, 2, 'Software Conformance Report', XLSWriter.style_title)
        report_datetime = get_datetime_string(self.conformance_report.created_time) + \
            ' UTC' if self.locale_datetime is None else self.locale_datetime
            
        self.ws.write(1, 2, report_datetime, XLSWriter.style_center )
        
        self.ws.write(4, 0, 'Summary: ', XLSWriter.style_bold)
        self.ws.write(6, 0, 'Total Hosts: %d' % len(self.conformance_report.entries), XLSWriter.style_summary)
        self.ws.write(7, 0, 'Match Criteria: ' + (self.conformance_report.match_criteria + ' packages').title(), XLSWriter.style_summary)
        self.ws.write(8, 0, 'Results:', XLSWriter.style_summary)
        
        if self.conformance_report.host_not_in_conformance == 0:
            self.ws.write(9, 0, "     All host(s) have conformed to the selected software profile", XLSWriter.style_summary)
        else:
            self.ws.write(9, 0, "     %d host(s) are not in complete conformance (see the 'Missing Packages' column)" 
                % self.conformance_report.host_not_in_conformance, XLSWriter.style_summary)
                        
        if self.conformance_report.host_out_dated_inventory > 0:
            self.ws.write(10, 0, "     %d host(s) may have out-dated inventory information (see '*' in the 'Conformed' column)"
                % self.conformance_report.host_out_dated_inventory, XLSWriter.style_summary)
        
    def write_software_profile_info(self):
        self.ws.write(self.row, 0, 'Software Profile: ' + self.conformance_report.software_profile, XLSWriter.style_bold)
        self.row += 2
    
        profile_packages = self.conformance_report.software_profile_packages.split(',')
        
        smu_loader = None
        platform, release = get_platform_and_release(profile_packages)
        if platform != UNKNOWN and release != UNKNOWN:
            smu_loader = SMUInfoLoader(platform, release)
        
        for profile_package in profile_packages:
            self.ws.write(self.row, 0, profile_package)
            if smu_loader is not None:
                smu_info = smu_loader.get_smu_info(profile_package.replace('.' + smu_loader.file_suffix,''))
                if smu_info is not None:
                    self.ws.write(self.row, 1, smu_info.description)
            
            self.row += 1  
        
        self.row += 1
        
    def write_host_info(self):
        entries = self.conformance_report.entries
    
        self.ws.write(self.row, 0, 'Hostname', XLSWriter.style_bold)
        self.ws.write(self.row, 1, 'Platform Software', XLSWriter.style_bold)
        
        if self.include_host_packages:
            if self.conformance_report.match_criteria == 'inactive':
                self.ws.write(self.row, 2, 'Installed Packages', XLSWriter.style_bold)
            else:
                self.ws.write(self.row, 2, 'Active Packages', XLSWriter.style_bold)
            
        self.ws.write(self.row, 3 if self.include_host_packages else 2, 'Missing Packages', XLSWriter.style_bold)
        self.ws.write(self.row, 4 if self.include_host_packages else 3, 'Conformed', XLSWriter.style_bold)
    
        self.row += 2
    
        for entry in entries:    
            if self.include_host_packages:        
                host_packages = entry.host_packages.split(',')
            else:
                host_packages = []
                
            missing_packages = entry.missing_packages.split(',')            
            lines = max(len(host_packages), len(missing_packages) )
            
            for line in range(lines):
                if line == 0:
                    self.ws.write(self.row, 0, entry.hostname)
                    self.ws.write(self.row, 1, entry.platform_software)
                    
                    out_dated_marker = '*' if entry.inventory_status != JobStatus.COMPLETED else ''
                    
                    # Update the Conform column
                    if entry.missing_packages:
                        self.ws.write(self.row, 4 if self.include_host_packages else 3, 'No (' + entry.last_successful_retrieval + ') ' + out_dated_marker)
                    else:
                        self.ws.write(self.row, 4 if self.include_host_packages else 3, 'Yes (' + entry.last_successful_retrieval + ') ' + out_dated_marker)
                
                if self.include_host_packages and line < len(host_packages):                    
                    self.ws.write(self.row, 2, host_packages[line])
                    
                if line < len(missing_packages):
                    self.ws.write(self.row, 3 if self.include_host_packages else 2, missing_packages[line])
                
                self.row += 1
                
            self.row += 1
