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
import xlwt

from filters import get_datetime_string
from smu_info_loader import SMUInfoLoader

from utils import is_empty
from utils import create_directory
from utils import create_temp_user_directory
from utils import make_file_writable

from report_writer import ReportWriter

from constants import UNKNOWN
from constants import HostConformanceStatus

import os


class ConformanceReportWriter(ReportWriter):
    def __init__(self, **kwargs):
        super(ConformanceReportWriter, self).__init__(**kwargs)
        self.style_title = xlwt.easyxf('font: height 350, bold on; align: vert centre, horiz center;')
        self.style_bold = xlwt.easyxf('font: bold on, height 260;')
        self.style_summary = xlwt.easyxf('font: height 220;')
        self.style_center = xlwt.easyxf('align: vert centre, horiz center;')

        self.user = kwargs.pop('user')
        self.conformance_report = kwargs.pop('conformance_report')
        self.locale_datetime = kwargs.pop('locale_datetime')
        self.include_host_packages = kwargs.pop('include_host_packages')
        self.exclude_conforming_hosts = kwargs.pop('exclude_conforming_hosts')

        self.wb = xlwt.Workbook()
        self.ws = self.wb.add_sheet('Conformance Report')
        self.ws.set_portrait(False)

        temp_user_dir = create_temp_user_directory(self.user.username)
        self.output_file_directory = os.path.normpath(os.path.join(temp_user_dir, "conformance_report"))

        create_directory(self.output_file_directory)
        make_file_writable(self.output_file_directory)

        self.row = 0
    
    def write_report(self):
        # Fit for Landscape mode
        self.ws.col(0).width = 7000
        self.ws.col(1).width = 5000
        self.ws.col(2).width = 8000
        self.ws.col(3).width = 8000
        self.ws.col(4).width = 5000

        self.write_header_info()

        self.row = 12
        self.write_software_profile_info()
        self.write_host_info()

        output_file_path = os.path.join(self.output_file_directory, 'conformance_report.xls')
        self.wb.save(output_file_path)

        return output_file_path

    def write_header_info(self):
        self.ws.write(0, 2, 'Software Conformance Report', self.style_title)
        report_datetime = get_datetime_string(self.conformance_report.created_time) + \
            ' UTC' if self.locale_datetime is None else self.locale_datetime
            
        self.ws.write(1, 2, report_datetime, self.style_center)

        self.ws.write(4, 0, 'Summary: ', self.style_bold)

        total_hosts = 0 if is_empty(self.conformance_report.hostnames) else \
            len(self.conformance_report.hostnames.split(','))

        self.ws.write(6, 0, 'Total Hosts: %d' % total_hosts, self.style_summary)
        self.ws.write(7, 0, 'Match Criteria: ' + (self.conformance_report.match_criteria + ' packages').title(),
                      self.style_summary)
        self.ws.write(8, 0, 'Results:', self.style_summary)
        
        if self.conformance_report.host_not_in_conformance == 0:
            self.ws.write(9, 0, "     All hosts are in complete conformance", self.style_summary)
        else:
            self.ws.write(9, 0, "     %d %s in complete conformance (see the 'Missing Packages' column)"
                % (self.conformance_report.host_not_in_conformance,
                    "hosts are not" if self.conformance_report.host_not_in_conformance > 1 else "host is not"),
                    self.style_summary)
                        
        if self.conformance_report.host_out_dated_inventory > 0:
            self.ws.write(10, 0, "     %d %s failed last software inventory retrieval (see '*' in the 'Is Conformed' column)"
                % (self.conformance_report.host_out_dated_inventory,
                    "hosts" if self.conformance_report.host_out_dated_inventory > 1 else "host"),
                    self.style_summary)
        
    def write_software_profile_info(self):
        self.ws.write(self.row, 0, 'Software Profile: ' + self.conformance_report.software_profile, self.style_bold)
        self.row += 2
    
        software_profile_packages = self.conformance_report.software_profile_packages.split(',')
        
        smu_loader = None
        platform, release = SMUInfoLoader.get_platform_and_release(software_profile_packages)
        if platform != UNKNOWN and release != UNKNOWN:
            smu_loader = SMUInfoLoader(platform, release)
        
        for software_profile_package in software_profile_packages:
            self.ws.write(self.row, 0, software_profile_package)
            if smu_loader is not None and smu_loader.is_valid:
                smu_info = smu_loader.get_smu_info(software_profile_package.replace('.' + smu_loader.file_suffix,''))
                if smu_info is not None:
                    self.ws.write(self.row, 1, smu_info.description)
            
            self.row += 1  
        
        self.row += 1
        
    def write_host_info(self):
        entries = self.conformance_report.entries

        if self.exclude_conforming_hosts:
            self.ws.write(self.row, 2, '(Only Non-conforming Hosts are Listed)', self.style_bold)
            self.row += 2

        self.ws.write(self.row, 0, 'Hostname', self.style_bold)
        self.ws.write(self.row, 1, 'Software', self.style_bold)
        
        if self.include_host_packages:
            if self.conformance_report.match_criteria == 'inactive':
                self.ws.write(self.row, 2, 'Inactive Packages', self.style_bold)
            else:
                self.ws.write(self.row, 2, 'Active Packages', self.style_bold)
            
        self.ws.write(self.row, 3 if self.include_host_packages else 2, 'Missing Packages', self.style_bold)
        self.ws.write(self.row, 4 if self.include_host_packages else 3, 'Is Conformed', self.style_bold)
    
        self.row += 2

        host_packages = []
        for entry in entries:
            if self.exclude_conforming_hosts and entry.conformed == HostConformanceStatus.CONFORM:
                continue

            if self.include_host_packages:        
                host_packages = entry.host_packages.split(',')

            missing_packages = entry.missing_packages.split(',')            
            lines = max(len(host_packages), len(missing_packages) )
            
            for line in range(lines):
                if line == 0:
                    self.ws.write(self.row, 0, entry.hostname)
                    self.ws.write(self.row, 1, entry.software_platform + ' ' + entry.software_version)

                    conformed_with_comments = entry.conformed + ' ' + entry.comments
                    # Update the Conform column
                    if entry.missing_packages:
                        self.ws.write(self.row, 4 if self.include_host_packages else 3, conformed_with_comments)
                    else:
                        self.ws.write(self.row, 4 if self.include_host_packages else 3, conformed_with_comments)
                
                if self.include_host_packages and line < len(host_packages):
                    self.ws.write(self.row, 2, host_packages[line])
                    
                if line < len(missing_packages):
                    self.ws.write(self.row, 3 if self.include_host_packages else 2, missing_packages[line])
                
                self.row += 1
                
            self.row += 1
