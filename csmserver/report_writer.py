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

from utils import create_directory
from utils import create_temp_user_directory
from utils import make_file_writable

import xlwt
import os


class ReportWriter(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def write_report(self):
        """
        :return: must return the file path of the output file
        """
        raise NotImplementedError("Children must override write_report")


class ExportSoftwareInfoWriter(ReportWriter):
    def __init__(self, **kwargs):
        ReportWriter.__init__(self, **kwargs)
        self.user = kwargs.pop('user')
        self.smu_loader = kwargs.pop('smu_loader')
        self.smu_list = kwargs.pop('smu_list')
        self.sp_list = kwargs.pop('sp_list')

        self.smu_list = sorted(self.smu_list, key=lambda x: x.posted_date, reverse=True)
        self.sp_list = sorted(self.sp_list, key=lambda x: x.posted_date, reverse=True)

        temp_user_dir = create_temp_user_directory(self.user.username)
        self.output_file_directory = os.path.normpath(os.path.join(temp_user_dir, "software_information_export"))

        create_directory(self.output_file_directory)
        make_file_writable(self.output_file_directory)


class ExportSoftwareInfoHTMLWriter(ExportSoftwareInfoWriter):
    def __init__(self, **kwargs):
        ExportSoftwareInfoWriter.__init__(self, **kwargs)
        self.output_filename = 'software_information.html'

    def get_report_header(self):
        return '<center><b>Platform: ' + self.smu_loader.platform.upper().replace('_','-') + ', Release: ' + self.smu_loader.release + '</b></center>'

    def write_report_to_file(self, contents):
        output_file_path = os.path.join(self.output_file_directory, self.output_filename)
        with open(output_file_path, 'w') as output_file:
            output_file.write(contents)

        return output_file_path


class ExportSoftwareInfoHTMLConciseWriter(ExportSoftwareInfoHTMLWriter):
    def __init__(self, **kwargs):
        ExportSoftwareInfoHTMLWriter.__init__(self, **kwargs)

    def write_report(self):
        return self.write_report_to_file(self.get_concise_report())

    def get_concise_report(self):
        contents = self.get_report_header()
        contents += '<p>'
        contents += '<html><body>'
        contents += self.get_concise_report_contents(self.smu_loader, self.smu_list,
                                                     'Total SMUs: {}'.format(len(self.smu_list)))
        if len(self.sp_list) > 0:
            contents += '<p><p><p><p><p>'
            contents += self.get_concise_report_contents(self.smu_loader, self.sp_list,
                                                         'Total Service Packs: {}'.format(len(self.sp_list)))
        contents += '</body></html>'

        return contents

    def get_concise_report_contents(self, smu_loader, software_list, title):
        contents = title
        contents += '<table cellspacing=1 cellpadding=2 border=1 width=100%>' + \
                    '<tr>' + \
                    '<th><b>DDTS</b></th>' + \
                    '<th><b>Description</b></th>' + \
                    '<th><b>Type</b></th>' + \
                    '<th><b>Impact</b></th>' + \
                    '<th><b>Supersedes</b></th>' + \
                    '<th><b>Prerequisites</b></th>' + \
                    '<th><b>Posted Date</b></th>' + \
                    '</tr>'

        for entry in software_list:
            supersedes = smu_loader.get_ddts_from_names(entry.supersedes.split(','))
            prerequisites = smu_loader.get_ddts_from_names(entry.prerequisites.split(','))

            contents += '<tr>' + \
                '<td>' + entry.ddts + '</td>' + \
                '<td>' + entry.description + '</td>' + \
                '<td>' + entry.type + '</td>' + \
                '<td>' + entry.impact + '</td>' + \
                '<td>' + ('None' if not supersedes else '<br>'.join(supersedes)) + '</td>' + \
                '<td>' + ('None' if not prerequisites else '<br>'.join(prerequisites)) + '</td>' + \
                '<td>' + entry.posted_date.split()[0] + '</td>' + \
                '</tr>'

        contents += '</table>'

        return contents


class ExportSoftwareInfoHTMLDefaultWriter(ExportSoftwareInfoHTMLWriter):
    def __init__(self, **kwargs):
        ExportSoftwareInfoHTMLWriter.__init__(self, **kwargs)

    def write_report(self):
        return self.write_report_to_file(self.get_default_report())

    def get_default_report(self):
        contents = self.get_report_header()
        contents += '<p>'
        contents += '<html><body>'
        contents += self.get_default_report_contents(self.smu_loader, self.smu_list,
                                                     'Total SMUs: {}'.format(len(self.smu_list)))

        if len(self.sp_list) > 0:
            contents += '<p><p><p><p><p>'
            contents += self.get_default_report_contents(self.smu_loader, self.sp_list,
                                                         'Total Service Packs: {}'.format(len(self.sp_list)))
        contents += '</body></html>'

        return contents

    def get_default_report_contents(self, smu_loader, software_list, title):
        contents = title
        contents += '<table cellspacing=1 cellpadding=2 border=1 width=100%>' + \
                    '<tr>' + \
                    '<th><b>ID</b></th>' + \
                    '<th><b>DDTS</b></th>' + \
                    '<th><b>Description</b></th>' + \
                    '<th><b>Type</b></th>' + \
                    '<th><b>Impact</b></th>' + \
                    '<th><b>Functional Areas</b></th>' + \
                    '<th><b>Posted Date</b></th>' + \
                    '</tr>'

        for entry in software_list:
            contents += '<tr>' + \
                '<td>' + entry.id + '</td>' + \
                '<td>' + entry.ddts + '</td>' + \
                '<td>' + entry.description + '</td>' + \
                '<td>' + entry.type + '</td>' + \
                '<td>' + entry.impact + '</td>' + \
                '<td>' + entry.functional_areas.replace(',', '<br>') + '</td>' + \
                '<td>' + entry.posted_date.split()[0] + '</td>' + \
                '</tr>'

        contents += '</table>'

        return contents


class ExportSoftwareInfoExcelWriter(ExportSoftwareInfoWriter):
    def __init__(self, **kwargs):
        ExportSoftwareInfoWriter.__init__(self, **kwargs)

        self.style_title = xlwt.easyxf('font: height 350, bold on; align: vert centre, horiz center;')
        self.style_bold = xlwt.easyxf('font: bold on, height 260;')
        self.style_summary = xlwt.easyxf('font: height 220;')
        self.style_center = xlwt.easyxf('align: vert centre, horiz center;')

        self.wb = xlwt.Workbook()
        self.ws = self.wb.add_sheet('Software Information Report')
        self.ws.set_portrait(False)

        self.output_filename = 'software_information.xls'
        self.row = 0

    def next_row(self):
        self.row += 1
        return self.row

    def get_report_header(self):
        return 'Platform: ' + self.smu_loader.platform.upper().replace('_','-') + ', Release: ' + self.smu_loader.release

    def write_report_to_file(self):
        output_file_path = os.path.join(self.output_file_directory, self.output_filename)
        self.wb.save(output_file_path)

        return output_file_path


class ExportSoftwareInfoExcelConciseWriter(ExportSoftwareInfoExcelWriter):
    def __init__(self, **kwargs):
        ExportSoftwareInfoExcelWriter.__init__(self, **kwargs)

    def write_report(self):
        self.ws.write(self.row, 2, self.get_report_header(), self.style_title)
        self.next_row()

        self.write_concise_report_contents(self.smu_loader, self.smu_list,
                                           'Total SMUs: {}'.format(len(self.smu_list)))

        if len(self.sp_list) > 0:
            self.row += 4
            self.write_concise_report_contents(self.smu_loader, self.sp_list,
                                               'Total Service Packs: {}'.format(len(self.sp_list)))

        return self.write_report_to_file()

    def write_concise_report_contents(self, smu_loader, software_list, title):
        # Fit for Landscape mode
        self.ws.col(0).width = 4000
        self.ws.col(1).width = 16000
        self.ws.col(2).width = 4000
        self.ws.col(3).width = 4000
        self.ws.col(4).width = 4000
        self.ws.col(5).width = 4000
        self.ws.col(6).width = 4000

        self.ws.write(self.row, 0, title, self.style_bold)
        self.next_row()

        self.ws.write(self.row, 0, 'DDTS', self.style_bold)
        self.ws.write(self.row, 1, 'Description', self.style_bold)
        self.ws.write(self.row, 2, 'Type', self.style_bold)
        self.ws.write(self.row, 3, 'Impact', self.style_bold)
        self.ws.write(self.row, 4, 'Supersedes', self.style_bold)
        self.ws.write(self.row, 5, 'Prerequisites', self.style_bold)
        self.ws.write(self.row, 6, 'Posted Date', self.style_bold)

        for entry in software_list:
            supersedes = smu_loader.get_ddts_from_names(entry.supersedes.split(','))
            prerequisites = smu_loader.get_ddts_from_names(entry.prerequisites.split(','))

            total_rows = max(len(supersedes) if len(supersedes) > len(prerequisites) else len(prerequisites), 1)
            for row in range(total_rows):
                self.next_row()

                if row == 0:
                    self.ws.write(self.row, 0, entry.ddts)
                    self.ws.write(self.row, 1, entry.description)
                    self.ws.write(self.row, 2, entry.type)
                    self.ws.write(self.row, 3, entry.impact)
                    self.ws.write(self.row, 6, entry.posted_date.split()[0])

                if row < len(supersedes):
                    self.ws.write(self.row, 4, supersedes[row])

                if row < len(prerequisites):
                    self.ws.write(self.row, 5, prerequisites[row])


class ExportSoftwareInfoExcelDefaultWriter(ExportSoftwareInfoExcelWriter):
    def __init__(self, **kwargs):
        ExportSoftwareInfoExcelWriter.__init__(self, **kwargs)

    def write_report(self):
        self.ws.write(self.row, 2, self.get_report_header(), self.style_title)
        self.next_row()

        self.write_default_report_contents(self.smu_loader, self.smu_list,
                                           'Total SMUs: {}'.format(len(self.smu_list)))

        if len(self.sp_list) > 0:
            self.row += 4
            self.write_default_report_contents(self.smu_loader, self.sp_list,
                                               'Total Service Packs: {}'.format(len(self.sp_list)))

        return self.write_report_to_file()

    def write_default_report_contents(self, smu_loader, software_list, title):
        # Fit for Landscape mode
        self.ws.col(0).width = 4000
        self.ws.col(1).width = 4000
        self.ws.col(2).width = 16000
        self.ws.col(3).width = 4000
        self.ws.col(4).width = 4000
        self.ws.col(5).width = 5000
        self.ws.col(6).width = 4000

        self.ws.write(self.row, 0, title, self.style_bold)
        self.next_row()

        self.ws.write(self.row, 0, 'ID', self.style_bold)
        self.ws.write(self.row, 1, 'DDTS', self.style_bold)
        self.ws.write(self.row, 2, 'Description', self.style_bold)
        self.ws.write(self.row, 3, 'Type', self.style_bold)
        self.ws.write(self.row, 4, 'Impact', self.style_bold)
        self.ws.write(self.row, 5, 'Functional Areas', self.style_bold)
        self.ws.write(self.row, 6, 'Posted Date', self.style_bold)

        for entry in software_list:
            functional_areas = entry.functional_areas.split(',')
            total_rows = max(len(functional_areas), 1)
            for row in range(total_rows):
                self.next_row()

                if row == 0:
                    self.ws.write(self.row, 0, entry.id)
                    self.ws.write(self.row, 1, entry.ddts)
                    self.ws.write(self.row, 2, entry.description)
                    self.ws.write(self.row, 3, entry.type)
                    self.ws.write(self.row, 4, entry.impact)
                    self.ws.write(self.row, 6, entry.posted_date.split()[0])

                if row < len(functional_areas):
                    self.ws.write(self.row, 5, functional_areas[row])
