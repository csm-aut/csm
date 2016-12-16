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

from common import get_last_successful_inventory_elapsed_time
from utils import create_directory
from utils import create_temp_user_directory
from utils import make_file_writable

import csv
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
        self.output_file_directory = os.path.normpath(os.path.join(temp_user_dir, 'software_information_export'))

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


class ExportInventoryInfoWriter(ReportWriter):
    def __init__(self, **kwargs):
        ReportWriter.__init__(self, **kwargs)
        self.user = kwargs.pop('user')
        self.serial_number = kwargs.pop('serial_number')
        self.region_names = kwargs.pop('region_names')
        self.chassis_types = kwargs.pop('chassis_types')
        self.software_versions = kwargs.pop('software_versions')
        self.model_names = kwargs.pop('model_names')
        self.partial_model_names = kwargs.pop('partial_model_names')

        self.available_inventory_iter = kwargs.pop('available_inventory_iter')
        self.in_use_inventory_iter = kwargs.pop('in_use_inventory_iter')

        temp_user_dir = create_temp_user_directory(self.user.username)
        self.output_file_directory = os.path.normpath(os.path.join(temp_user_dir, 'inventory_information_export'))

        create_directory(self.output_file_directory)
        make_file_writable(self.output_file_directory)


class ExportInventoryInfoHTMLWriter(ExportInventoryInfoWriter):
    def __init__(self, **kwargs):
        ExportInventoryInfoWriter.__init__(self, **kwargs)

    def get_report_header(self):

        html = get_search_filter_in_html(self.__dict__)

        if html:
            return '<b><p>Search Filter(s):</p>' + html + '</b>'

        return '<p><b>Search Filter(s): None</b></p>'

    def write_report(self):
        output_file_path = os.path.join(self.output_file_directory, 'inventory_information.html')
        with open(output_file_path, 'w') as output_file:
            output_file.write(self.get_content())

        return output_file_path

    def get_content(self):
        content = self.get_report_header()
        content += '<p>'
        content += '<html><body>'
        content += self.get_in_use_inventory_table_content()
        content += '<p><p><p><p><p>'
        content += self.get_available_inventory_table_content()
        content += '</body></html>'

        return content

    def get_available_inventory_table_content(self):
        content = '<b>Number of Available Inventories: {}</b>'.format(str(self.available_inventory_iter.count()))
        if self.available_inventory_iter.count() > 0:
            content += '<table cellspacing=1 cellpadding=2 border=1 width=100%>' + \
                        '<tr>' + \
                        '<th><b>Model Name</b></th>' + \
                        '<th><b>Serial Number</b></th>' + \
                        '<th><b>Description</b></th>' + \
                        '<th><b>Notes</b></th>' + \
                        '</tr>'

            for inventory in self.available_inventory_iter:
                content += '<tr>' + \
                    '<td>' + (inventory.model_name if inventory.model_name else '') + '</td>' + \
                    '<td>' + (inventory.serial_number if inventory.serial_number else '') + '</td>' + \
                    '<td>' + (inventory.description if inventory.description else '') + '</td>' + \
                    '<td>' + (inventory.notes if inventory.notes else '') + '</td>' + \
                    '</tr>'

            content += '</table>'

        return content

    def get_in_use_inventory_table_content(self):
        content = '<b>Number of In Use Inventories: {}</b>'.format(str(self.in_use_inventory_iter.count()))
        if self.in_use_inventory_iter.count() > 0:
            content += '<table cellspacing=1 cellpadding=2 border=1 width=100%>' + \
                       '<tr>' + \
                       '<th><b>Model Name</b></th>' + \
                       '<th><b>Name</b></th>' + \
                       '<th><b>Serial Number</b></th>' + \
                       '<th><b>Description</b></th>' + \
                       '<th><b>Hostname</b></th>' + \
                       '<th><b>Chassis</b></th>' + \
                       '<th><b>Platform</b></th>' + \
                       '<th><b>Software</b></th>' + \
                       '<th><b>Region</b></th>' + \
                       '<th><b>Location</b></th>' + \
                       '<th><b>Last Successful Retrieval</b></th>' + \
                       '</tr>'

            for inventory in self.in_use_inventory_iter:
                content += '<tr>' + \
                           '<td>' + (inventory.model_name if inventory.model_name else '') + '</td>' + \
                           '<td>' + (inventory.name if inventory.name else '') + '</td>' + \
                           '<td>' + (inventory.serial_number if inventory.serial_number else '') + '</td>' + \
                           '<td>' + (inventory.description if inventory.description else '') + '</td>'

                host = inventory.host
                if host:
                    inventory_job = host.inventory_job[0]
                    if inventory_job and inventory_job.last_successful_time:
                        last_successful_retrieval = get_last_successful_inventory_elapsed_time(host)
                    else:
                        last_successful_retrieval = ''
                    content += '<td>' + (host.hostname if host.hostname else '') + '</td>' + \
                               '<td>' + (host.platform if host.platform else '') + '</td>' + \
                               '<td>' + (host.software_platform if host.software_platform else '') + '</td>' + \
                               '<td>' + (host.software_version if host.software_version else '') + '</td>' + \
                               '<td>' + (host.region.name if host.region.name else '') + '</td>' + \
                               '<td>' + (host.location if host.location else '') + '</td>' + \
                               '<td>' + last_successful_retrieval + '</td>' + \
                               '</tr>'
                else:
                    content += '<td></td>' + '<td></td>' + '<td></td>' + \
                               '<td></td>' + '<td></td>' + '<td></td>' + '<td></td>'\
                               '</tr>'

            content += '</table>'

        return content


# public function - used in inventory too
def get_search_filter_in_html(filters_dict):
    html = ''
    html += check_and_add_search_filter('Serial Number', filters_dict.get('serial_number'))
    html += check_and_add_search_filter('Region', filters_dict.get('region_names'))
    html += check_and_add_search_filter('Chassis', filters_dict.get('chassis_types'))
    html += check_and_add_search_filter('Software', filters_dict.get('software_versions'))
    html += check_and_add_search_filter('Model Names', filters_dict.get('model_names'))
    html += check_and_add_search_filter('Partial Model Names', filters_dict.get('partial_model_names'))
    if html:
        return '<ul>' + html + '</ul>'

    return html


def check_and_add_search_filter(filter_title, filter_value):
    if filter_value:
        if isinstance(filter_value, list):
            return '<li>{}: '.format(filter_title) + ',&nbsp;'.join(filter_value) + '</li>'
        else:
            return '<li>{}: '.format(filter_title) + filter_value + '</li>'

    return ''


class ExportInventoryInfoExcelWriter(ExportInventoryInfoWriter):
    def __init__(self, **kwargs):
        ExportInventoryInfoWriter.__init__(self, **kwargs)
        self.style_title = xlwt.easyxf('font: height 350, bold on; align: vert centre;')
        self.style_bold = xlwt.easyxf('font: bold on, height 260;')
        self.style_summary = xlwt.easyxf('font: height 220;')
        self.style_center = xlwt.easyxf('align: vert centre, horiz center;')

        self.wb = xlwt.Workbook()
        self.ws = self.wb.add_sheet('Inventory Information Report')
        self.ws.set_portrait(False)

        self.row = 0

    def next_row(self):
        self.row += 1
        return self.row

    def write_report_header(self):
        if not self.serial_number and not self.region_names and not self.chassis_types and \
                not self.software_versions and not self.model_names and not self.partial_model_names:
            self.ws.write(self.row, 0, 'Search Filter(s): None', self.style_title)
        else:
            self.ws.write(self.row, 0, 'Search Filter(s):', self.style_title)
        self.next_row()
        if self.serial_number:
            self.ws.write(self.row, 1, 'Serial Number: ' + self.serial_number, self.style_title)
            self.next_row()
        if self.region_names:
            self.ws.write(self.row, 1, 'Region: ' + ', '.join(self.region_names), self.style_title)
            self.next_row()
        if self.chassis_types:
            self.ws.write(self.row, 1, 'Chassis: ' + ', '.join(self.chassis_types), self.style_title)
            self.next_row()
        if self.software_versions:
            self.ws.write(self.row, 1, 'Software: ' + ', '.join(self.software_versions), self.style_title)
            self.next_row()
        if self.model_names:
            self.ws.write(self.row, 1, 'Model Names: ' + ', '.join(self.model_names), self.style_title)
            self.next_row()
        if self.partial_model_names:
            self.ws.write(self.row, 1, 'Partial Model Names: ' + ', '.join(self.partial_model_names), self.style_title)
            self.next_row()

        return

    def write_report(self):
        self.write_report_header()
        self.next_row()
        self.write_report_contents()

        output_file_path = os.path.join(self.output_file_directory, 'inventory_information.xls')
        self.wb.save(output_file_path)

        return output_file_path

    def write_report_contents(self):
        # Fit for Landscape mode
        self.ws.col(0).width = 5000
        self.ws.col(1).width = 8500
        self.ws.col(2).width = 4000
        self.ws.col(3).width = 13000
        self.ws.col(4).width = 4000
        self.ws.col(5).width = 4000
        self.ws.col(6).width = 4000
        self.ws.col(7).width = 4000
        self.ws.col(8).width = 5000
        self.ws.col(9).width = 5000
        self.ws.col(10).width = 5000

        self.write_in_use_inventory_table_content()
        self.next_row()
        self.next_row()
        self.next_row()
        self.write_available_inventory_table_content()

        return

    def write_available_inventory_table_content(self):
        self.ws.write(self.row, 0, 'Number of Available Inventories: ' + str(self.available_inventory_iter.count()),
                      self.style_bold)
        if self.available_inventory_iter.count() > 0:
            self.next_row()
            self.ws.write(self.row, 0, 'Model Name', self.style_bold)
            self.ws.write(self.row, 1, 'Serial Number', self.style_bold)
            self.ws.write(self.row, 2, 'Description', self.style_bold)
            self.ws.write(self.row, 3, 'Notes', self.style_bold)

            for inventory in self.available_inventory_iter:
                self.next_row()
                self.ws.write(self.row, 0, (inventory.model_name if inventory.model_name else ''))
                self.ws.write(self.row, 1, (inventory.serial_number if inventory.serial_number else ''))
                self.ws.write(self.row, 2, (inventory.description if inventory.description else ''))
                self.ws.write(self.row, 3, (inventory.notes if inventory.notes else ''))

        return

    def write_in_use_inventory_table_content(self):
        self.ws.write(self.row, 0, 'Number of In Use Inventories: ' + str(self.in_use_inventory_iter.count()),
                      self.style_bold)
        if self.in_use_inventory_iter.count() > 0:
            self.next_row()
            self.ws.write(self.row, 0, 'Model Name', self.style_bold)
            self.ws.write(self.row, 1, 'Name', self.style_bold)
            self.ws.write(self.row, 2, 'Serial Number', self.style_bold)
            self.ws.write(self.row, 3, 'Description', self.style_bold)
            self.ws.write(self.row, 4, 'Hostname', self.style_bold)
            self.ws.write(self.row, 5, 'Chassis', self.style_bold)
            self.ws.write(self.row, 6, 'Platform', self.style_bold)
            self.ws.write(self.row, 7, 'Software', self.style_bold)
            self.ws.write(self.row, 8, 'Region', self.style_bold)
            self.ws.write(self.row, 9, 'Location', self.style_bold)
            self.ws.write(self.row, 10, 'Last Successful Retrieval', self.style_bold)

            for inventory in self.in_use_inventory_iter:
                self.next_row()
                self.ws.write(self.row, 0, (inventory.model_name if inventory.model_name else ''))
                self.ws.write(self.row, 1, (inventory.name if inventory.name else ''))
                self.ws.write(self.row, 2, (inventory.serial_number if inventory.serial_number else ''))
                self.ws.write(self.row, 3, (inventory.description if inventory.description else ''))

                host = inventory.host
                if host:
                    inventory_job = host.inventory_job[0]
                    if inventory_job and inventory_job.last_successful_time:
                        last_successful_retrieval = get_last_successful_inventory_elapsed_time(host)
                    else:
                        last_successful_retrieval = ''
                    self.ws.write(self.row, 4, (host.hostname if host.hostname else ''))
                    self.ws.write(self.row, 5, (host.platform if host.platform else ''))
                    self.ws.write(self.row, 6, (host.software_platform if host.software_platform else ''))
                    self.ws.write(self.row, 7, (host.software_version if host.software_version else ''))
                    self.ws.write(self.row, 8, (host.region.name if host.region.name else ''))
                    self.ws.write(self.row, 9, (host.location if host.location else ''))
                    self.ws.write(self.row, 10, last_successful_retrieval)

        return


class ExportInventoryInfoCSVWriter(ExportInventoryInfoWriter):
    def __init__(self, **kwargs):
        ExportInventoryInfoWriter.__init__(self, **kwargs)

    def write_report_header(self, csv_writer):
        if not self.serial_number and not self.region_names and not self.chassis_types and \
                not self.software_versions and not self.model_names and not self.partial_model_names:
            csv_writer.writerow(['Search Filter(s): None'])
            return
        else:
            csv_writer.writerow(['Search Filter(s):'])
            prepare_row = []

        if self.serial_number:
            prepare_row.append(('Serial Number: ' + self.serial_number))
        if self.region_names:
            prepare_row.append(('Region: ' + ', '.join(self.region_names)))
        if self.chassis_types:
            prepare_row.append(('Chassis: ' + ', '.join(self.chassis_types)))
        if self.software_versions:
            prepare_row.append(('Software: ' + ', '.join(self.software_versions)))
        if self.model_names:
            prepare_row.append(('Model Names: ' + ', '.join(self.model_names)))
        if self.partial_model_names:
            prepare_row.append(('Partial Model Names: ' + ', '.join(self.partial_model_names)))

        csv_writer.writerow(prepare_row)
        return

    def write_report(self):
        output_file_path = os.path.join(self.output_file_directory, 'inventory_information.csv')

        with open(output_file_path, 'w') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',')
            self.write_report_header(csv_writer)
            csv_writer.writerow([])
            self.write_report_contents(csv_writer)

        return output_file_path

    def write_report_contents(self, csv_writer):
        self.write_in_use_inventory_table_content(csv_writer)
        csv_writer.writerow([])
        self.write_available_inventory_table_content(csv_writer)
        return

    def write_available_inventory_table_content(self, csv_writer):
        csv_writer.writerow(['Number of Available Inventories: ' + str(self.available_inventory_iter.count())])

        if self.available_inventory_iter.count() > 0:

            csv_writer.writerow(['Model Name', 'Serial Number', 'Description', 'Notes'])

            for inventory in self.available_inventory_iter:
                csv_writer.writerow([(inventory.model_name if inventory.model_name else ''),
                                     (inventory.serial_number if inventory.serial_number else ''),
                                     (inventory.description if inventory.description else ''),
                                     (inventory.notes if inventory.notes else '')])

        return

    def write_in_use_inventory_table_content(self, csv_writer):
        csv_writer.writerow(['Number of In Use Inventories: ' + str(self.in_use_inventory_iter.count())])

        if self.in_use_inventory_iter.count() > 0:
            csv_writer.writerow(['Model Name', 'Name', 'Serial Number', 'Description', 'Hostname', 'Chassis',
                                 'Platform', 'Software', 'Region', 'Location', 'Last Successful Retrieval'])

            for inventory in self.in_use_inventory_iter:
                prepare_row = [(inventory.model_name if inventory.model_name else ''),
                               (inventory.name if inventory.name else ''),
                               (inventory.serial_number if inventory.serial_number else ''),
                               (inventory.description if inventory.description else '')]

                host = inventory.host
                if host:
                    inventory_job = host.inventory_job[0]
                    if inventory_job and inventory_job.last_successful_time:
                        last_successful_retrieval = get_last_successful_inventory_elapsed_time(host)
                    else:
                        last_successful_retrieval = ''
                    prepare_row.extend([(host.hostname if host.hostname else ''),
                                       (host.platform if host.platform else ''),
                                       (host.software_platform if host.software_platform else ''),
                                       (host.software_version if host.software_version else ''),
                                       (host.region.name if host.region.name else ''),
                                       (host.location if host.location else ''),
                                       last_successful_retrieval])
                csv_writer.writerow(prepare_row)

        return


class ExportInventoryDashboardWriter(ReportWriter):
    def __init__(self, **kwargs):
        ReportWriter.__init__(self, **kwargs)
        self.user = kwargs.pop('user')
        self.region_name = kwargs.pop('region_name')

        self.chassis_summary_iter = kwargs.pop('chassis_summary_iter')
        self.model_name_summary_iter = kwargs.pop('model_name_summary_iter')

        self.inventory_without_serial_number_iter = kwargs.pop('inventory_without_serial_number_iter')
        self.inventory_with_duplicate_serial_number_iter = kwargs.pop('inventory_with_duplicate_serial_number_iter')

        temp_user_dir = create_temp_user_directory(self.user.username)
        self.output_file_directory = os.path.normpath(os.path.join(temp_user_dir, 'inventory_information_export'))

        create_directory(self.output_file_directory)
        make_file_writable(self.output_file_directory)


class ExportInventoryDashboardHTMLWriter(ExportInventoryDashboardWriter):
    def __init__(self, **kwargs):
        ExportInventoryDashboardWriter.__init__(self, **kwargs)

    def get_report_header(self):
        return '<b><p>Region:&nbsp;' + self.region_name + '</p></b>'

    def write_report(self):
        output_file_path = os.path.join(self.output_file_directory, 'inventory_dashboard_summary.html')
        with open(output_file_path, 'w') as output_file:
            output_file.write(self.get_content())

        return output_file_path

    def get_content(self):
        content = self.get_report_header()
        content += '<p>'
        content += '<html><body>'
        content += '<hr>'
        content += self.get_chassis_summary_table_content()
        content += '<br><hr>'
        content += self.get_model_name_summary_table_content()
        content += '<br><hr>'
        content += self.get_inventory_without_serial_number_table_content()
        content += '<br><hr>'
        content += self.get_inventory_with_duplicate_serial_number_table_content()
        content += '<br><hr>'
        content += '</body></html>'

        return content

    def get_chassis_summary_table_content(self):

        content = '<p><b>Total Chassis Types: {}</b></p>'.format(str(self.chassis_summary_iter.count()))
        grand_total = 0

        if self.chassis_summary_iter.count() > 0:
            content += '<table cellspacing=1 cellpadding=1 border=1 width=30%>' + \
                    '<tr>' + \
                    '<th><b>Chassis</b></th>' + \
                    '<th><b>Count</b></th>' + \
                    '</tr>'

            for chassis_type, count in self.chassis_summary_iter:
                content += '<tr>' + \
                    '<td>' + (chassis_type if chassis_type else '') + '</td>' + \
                    '<td>' + str(count) + '</td>' + \
                    '</tr>'
                grand_total += count

            content += '</table>'

        content = '<p><b>Total Chassis: ' + str(grand_total) + '</b></p>' + content

        return content

    def get_model_name_summary_table_content(self):

        total_pid_types = 0
        content = ''

        for table_dict in self.model_name_summary_iter:
            content += '<tr>' + \
                '<td>' + (table_dict['model_name']
                          if table_dict['model_name'] != '' else '(Undefined PID)') + '</td>' + \
                '<td>' + str(table_dict['in_use_count']) + '</td>' + \
                '<td>' + str(table_dict['available_count']) + '</td>' + \
                '</tr>'
            total_pid_types += 1

        if total_pid_types > 0:
            content = '<b><p>Total PID Types: {}</p>'.format(str(total_pid_types)) + \
                      '<p>Column "Available" refers to All Regions</p></b>' + \
                      '<table cellspacing=1 cellpadding=1 border=1 width=30%>' + \
                      '<tr>' + \
                      '<th><b>Model Name (PID)</b></th>' + \
                      '<th><b>In Use</b></th>' + \
                      '<th><b>Available</b></th>' + \
                      '</tr>' + content + '</table>'
        else:
            content = '<p><b>Total PID Types: 0</b></p>'

        return content

    def get_inventory_without_serial_number_table_content(self):
        content = '<b><p>Inventory without Serial Number</p>' + \
                  '<p>Total Hosts: {}</p></b>'.format(str(self.inventory_without_serial_number_iter.count()))

        if self.inventory_without_serial_number_iter.count() > 0:
            content += '<table cellspacing=1 cellpadding=1 border=1 width=30%>' + \
                       '<tr>' + \
                       '<th><b>Hostname</b></th>' + \
                       '<th><b>Count</b></th>' + \
                       '</tr>'

            for hostname, count in self.inventory_without_serial_number_iter:
                content += '<tr>' + \
                           '<td>' + (hostname if hostname else '') + '</td>' + \
                           '<td>' + str(count) + '</td>' + \
                           '</tr>'

            content += '</table>'

        return content

    def get_inventory_with_duplicate_serial_number_table_content(self):
        content = '<b><p>Inventory with Duplicate Serial Numbers</p>' + \
                  '<p>Total Duplicate Serial Numbers: {}</p></b>'.format(
                      str(self.inventory_with_duplicate_serial_number_iter.count()))

        if self.inventory_with_duplicate_serial_number_iter.count() > 0:
            content += '<table cellspacing=1 cellpadding=1 border=1 width=30%>' + \
                       '<tr>' + \
                       '<th><b>Serial Number</b></th>' + \
                       '<th><b>Count</b></th>' + \
                       '</tr>'

            for serial_number, count in self.inventory_with_duplicate_serial_number_iter:
                content += '<tr>' + \
                           '<td>' + (serial_number if serial_number else '(Undefined Serial Number)') + '</td>' + \
                           '<td>' + str(count) + '</td>' + \
                           '</tr>'

            content += '</table>'

        return content


class ExportInventoryDashboardExcelWriter(ExportInventoryDashboardWriter):
    def __init__(self, **kwargs):
        ExportInventoryDashboardWriter.__init__(self, **kwargs)
        self.style_title = xlwt.easyxf('font: height 350, bold on; align: vert centre;')
        self.style_bold = xlwt.easyxf('font: bold on, height 260;')
        self.style_summary = xlwt.easyxf('font: height 220;')
        self.style_center = xlwt.easyxf('align: vert centre, horiz center;')

        self.wb = xlwt.Workbook()
        self.ws = self.wb.add_sheet('Inventory Dashboard Summary')
        self.ws.set_portrait(False)

        self.row = 0

    def next_row(self):
        self.row += 1
        return self.row

    def write_report_header(self):
        if self.region_name:
            self.ws.write(self.row, 0, 'Region: ' + self.region_name, self.style_title)
        return

    def write_report(self):
        self.write_report_header()
        self.next_row()
        self.next_row()
        self.next_row()
        self.write_report_contents()

        output_file_path = os.path.join(self.output_file_directory, 'inventory_dashboard_summary.xls')
        self.wb.save(output_file_path)

        return output_file_path

    def write_report_contents(self):
        # Fit for Landscape mode
        self.ws.col(0).width = 5000
        self.ws.col(1).width = 3000
        self.ws.col(2).width = 3000

        self.write_chassis_summary_table_content()
        self.next_row()
        self.next_row()
        self.next_row()
        self.write_model_name_summary_table_content()
        self.next_row()
        self.next_row()
        self.next_row()
        self.write_inventory_without_serial_number_table_content()
        self.next_row()
        self.next_row()
        self.next_row()
        self.write_inventory_with_duplicate_serial_number_table_content()

        return

    def write_chassis_summary_table_content(self):
        header_row = self.row
        self.next_row()
        self.ws.write(self.row, 0, 'Total Chassis Types: ' + str(self.chassis_summary_iter.count()),
                      self.style_bold)
        grand_total = 0
        if self.chassis_summary_iter.count() > 0:
            self.next_row()
            self.ws.write(self.row, 0, 'Chassis', self.style_bold)
            self.ws.write(self.row, 1, 'Count', self.style_bold)

            for chassis_type, count in self.chassis_summary_iter:
                self.next_row()
                self.ws.write(self.row, 0, (chassis_type if chassis_type else ''))
                self.ws.write(self.row, 1, count)
                grand_total += count

        self.ws.write(header_row, 0, 'Total Chassis: ' + str(grand_total),
                      self.style_bold)

        return

    def write_model_name_summary_table_content(self):
        header_row = self.row
        self.next_row()
        self.next_row()
        total_pid_types = 0
        for table_dict in self.model_name_summary_iter:
            self.next_row()
            self.ws.write(self.row, 0, (table_dict['model_name']
                                        if table_dict['model_name'] != '' else '(Undefined PID)'))
            self.ws.write(self.row, 1, table_dict['in_use_count'])
            self.ws.write(self.row, 2, table_dict['available_count'])
            total_pid_types += 1

        if total_pid_types > 0:
            self.ws.write(header_row, 0, 'Total PID Types: ' + str(total_pid_types), self.style_bold)
            self.ws.write(header_row + 1, 0, 'Column "Available" refers to All Regions', self.style_bold)
            self.ws.write(header_row + 2, 0, 'Model Name (PID)', self.style_bold)
            self.ws.write(header_row + 2, 1, 'In Use', self.style_bold)
            self.ws.write(header_row + 2, 2, 'Available', self.style_bold)
        else :
            self.ws.write(header_row, 0, 'Total PID Types: 0', self.style_bold)
            self.row -= 2

        return

    def write_inventory_without_serial_number_table_content(self):
        self.ws.write(self.row, 0, 'Inventory without Serial Number', self.style_bold)
        self.next_row()
        self.ws.write(self.row, 0, 'Total Hosts: ' + str(self.inventory_without_serial_number_iter.count()),
                      self.style_bold)

        if self.inventory_without_serial_number_iter.count() > 0:
            self.next_row()
            self.ws.write(self.row, 0, 'Hostname', self.style_bold)
            self.ws.write(self.row, 1, 'Count', self.style_bold)

            for hostname, count in self.inventory_without_serial_number_iter:
                self.next_row()
                self.ws.write(self.row, 0, (hostname if hostname else ''))
                self.ws.write(self.row, 1, count)

        return

    def write_inventory_with_duplicate_serial_number_table_content(self):
        self.ws.write(self.row, 0, 'Inventory with Duplicate Serial Numbers', self.style_bold)
        self.next_row()
        self.ws.write(self.row, 0,
                      'Total Duplicate Serial Numbers: ' + str(self.inventory_with_duplicate_serial_number_iter.count()),
                      self.style_bold)
        self.next_row()
        if self.inventory_with_duplicate_serial_number_iter.count() > 0:
            self.ws.write(self.row, 0, 'Serial Number', self.style_bold)
            self.ws.write(self.row, 1, 'Count', self.style_bold)

            for serial_number, count in self.inventory_with_duplicate_serial_number_iter:
                self.next_row()
                self.ws.write(self.row, 0, (serial_number if serial_number else '(Undefined Serial Number)'))
                self.ws.write(self.row, 1, count)

        return


class ExportInventoryDashboardCSVWriter(ExportInventoryDashboardWriter):
    def __init__(self, **kwargs):
        ExportInventoryDashboardWriter.__init__(self, **kwargs)

    def write_report_header(self, csv_writer):
        csv_writer.writerow(['Region: ' + self.region_name])
        return

    def write_report(self):
        output_file_path = os.path.join(self.output_file_directory, 'inventory_dashboard_summary.csv')

        with open(output_file_path, 'w') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',')
            self.write_report_header(csv_writer)
            csv_writer.writerow([])
            self.write_report_contents(csv_writer)

        return output_file_path

    def write_report_contents(self, csv_writer):
        self.write_chassis_summary_table_content(csv_writer)
        csv_writer.writerow([])
        self.write_model_name_summary_table_content(csv_writer)
        csv_writer.writerow([])
        self.write_inventory_without_serial_number_table_content(csv_writer)
        csv_writer.writerow([])
        self.write_inventory_with_duplicate_serial_number_table_content(csv_writer)
        csv_writer.writerow([])
        return

    def write_chassis_summary_table_content(self, csv_writer):

        # reserve first spot for header
        prepare_rows = [['']]

        prepare_rows.append(['Total Chassis Types: ' + str(self.chassis_summary_iter.count())])

        grand_total = 0
        if self.chassis_summary_iter.count() > 0:

            prepare_rows.append(['Chassis', 'Count'])

            for chassis_type, count in self.chassis_summary_iter:
                prepare_rows.append([(chassis_type if chassis_type else ''), str(count)])
                grand_total += count

        prepare_rows[0] = ['Total Chassis: ' + str(grand_total)]
        csv_writer.writerows(prepare_rows)
        return

    def write_model_name_summary_table_content(self, csv_writer):

        # reserve first spots for headers
        prepare_rows = [[''], [''], ['']]

        total_pid_types = 0
        for table_dict in self.model_name_summary_iter:
            prepare_rows.append([(table_dict['model_name'] if table_dict['model_name'] != '' else '(Undefined PID)'),
                                 str(table_dict['in_use_count']),
                                 str(table_dict['available_count'])])
            total_pid_types += 1

        if total_pid_types > 0:
            prepare_rows[0] = ['Total PID Types: ' + str(total_pid_types)]
            prepare_rows[1] = ['Column "Available" refers to All Regions']
            prepare_rows[2] = ['Model Name (PID)', 'In Use', 'Available']
        else:
            prepare_rows = [['Total PID Types: 0']]

        csv_writer.writerows(prepare_rows)
        return

    def write_inventory_without_serial_number_table_content(self, csv_writer):

        csv_writer.writerow(['Inventory without Serial Number'])
        csv_writer.writerow(['Total Hosts: ' + str(self.inventory_without_serial_number_iter.count())])

        if self.inventory_without_serial_number_iter.count() > 0:
            csv_writer.writerow(['Hostname', 'Count'])

            for hostname, count in self.inventory_without_serial_number_iter:
                csv_writer.writerow([(hostname if hostname else ''), str(count)])

        return

    def write_inventory_with_duplicate_serial_number_table_content(self, csv_writer):

        csv_writer.writerow(['Inventory with Duplicate Serial Numbers'])
        csv_writer.writerow(['Total Duplicate Serial Numbers: ' + str(self.inventory_with_duplicate_serial_number_iter.count())])

        if self.inventory_with_duplicate_serial_number_iter.count() > 0:
            csv_writer.writerow(['Serial Number', 'Count'])

            for serial_number, count in self.inventory_with_duplicate_serial_number_iter:
                csv_writer.writerow([(serial_number if serial_number else '(Undefined Serial Number)'), str(count)])

        return
