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
import re

from models import Package
from models import Satellite

from constants import PackageState

from base import BaseSoftwarePackageParser
from base import BaseInventoryParser


class IOSXRSoftwarePackageParser(BaseSoftwarePackageParser):

    def process_software_packages(self, ctx):
        inactive_packages = {}
        active_packages = {}
        committed_packages = {}
        host_packages = []

        cli_show_install_inactive = ctx.load_data('cli_show_install_inactive')
        cli_show_install_active = ctx.load_data('cli_show_install_active')
        cli_show_install_committed = ctx.load_data('cli_show_install_committed')

        if isinstance(cli_show_install_inactive, list):
            inactive_packages = self.parseContents(cli_show_install_inactive[0], PackageState.INACTIVE)
        
        if isinstance(cli_show_install_active, list):
            active_packages = self.parseContents(cli_show_install_active[0], PackageState.ACTIVE)
        
        if isinstance(cli_show_install_committed, list):
            committed_packages = self.parseContents(cli_show_install_committed[0], PackageState.ACTIVE_COMMITTED)
        
        if committed_packages:
            for package in active_packages.values():
                if package.name in committed_packages:
                    package.state = PackageState.ACTIVE_COMMITTED
             
            for package in inactive_packages.values():
                if package.name in committed_packages:
                    # This is when the package is deactivated
                    package.state = PackageState.INACTIVE_COMMITTED
        
        for package in active_packages.values():
            host_packages.append(package)
            
        for package in inactive_packages.values():
            host_packages.append(package)
        
        if len(host_packages) > 0:
            ctx.host.packages = host_packages
            return True
        
        return False
        
    def parseContents(self, lines, package_state):
        package_dict = {}

        if lines is None:
            return package_dict

        found = False
        lines = lines.splitlines()

        for line in lines:
            if found:
                line = line.strip()

                if ':' in line:
                    location, name = line.split(':')
                else:
                    location = ''
                    name = line

                # skip anything after the blank line
                if len(line) == 0:
                    break
                
                package = Package(location=location, name=name, state=package_state)
                package_dict[name] = package

            elif 'Packages' in line:
                found = True

        return package_dict


class ASR9KInventoryParser(BaseInventoryParser):

    def parse_inventory_output(self, output):
        """
        Get everything except for the Generic Fan inventories from the inventory data
        """
        return [m.groupdict() for m in self.REGEX_BASIC_PATTERN.finditer(output)
                if 'Generic Fan' not in m.group('description')]


class IOSXRSatelliteParser():

    def process_satellites(self, ctx):
        satellites = list()

        # print "in process_satellites"
        cli_show_nv_satellite = ctx.load_data('cli_show_nv_satellite')

        # check if none, do nothing
        if not cli_show_nv_satellite or 'No satellites are configured' in cli_show_nv_satellite[0]:
            print("No satellites are configured")
            return

        '''
        RP/0/RP0/CPU0:AGN_PE_11_9k#show nv satellite status satellite 101
        Satellite 101
        -------------
          Status: Connected (Stable)
          Redundancy: Standby (Group: 100)
          Type: asr9000v
          Displayed device name: Sat101
          MAC address: 4055.3958.137c
          IPv4 address: 10.0.101.1 (auto, VRF: **nVSatellite)
          Serial Number: CAT1551B2HR
          Remote version: Compatible (latest version)
            ROMMON: 128.0 (Latest)
            FPGA: 1.13 (Latest)
            IOS: 622.101 (Latest)
          Received candidate fabric ports:
            nVFabric-GigE0/0/42-43 (permanent)
            nVFabric-TenGigE0/0/44-47 (permanent)
          Configured satellite fabric links:
            Bundle-Ether101
            ---------------
              Status: Satellite Ready
              Remote ports: GigabitEthernet0/0/0-4,24-28
              Discovered satellite fabric links:
                TenGigE0/3/0/0: Satellite Ready; No conflict
                TenGigE0/12/0/0/0: Satellite Ready; No conflict


        satellites.append(Satellite(
            satellite_id='101',
            device_name='Sat101',
            type='asr9000v',
            state='Connected',
            install_state='Stable',
            ip_address='10.0.101.1',
            serial_number='CAT1551B2HR',
            mac_address='4055.3958.137c',
            remote_version='Compatible (latest version)',
            remote_version_details='ROMMON: 128.0 (Latest),FPGA: 1.13 (Latest),IOS: 622.101 (Latest)',
            fabric_links='Bundle-Ether101'
        ))
        '''

        Satellite_id = ''
        Device_name = ''
        Type = ''
        State = ''
        Install_state = ''
        Mac_address = ''
        Ip_address = ''
        Serial_number = ''
        Remote_version = ''
        Remote_version_details_list = []
        Fabric_links_list = []

        remote_version_flag = False
        fabric_links_flag = False
        print_flag = False

        lines = cli_show_nv_satellite[0].split('\n')
        lines = [x for x in lines if x]

        for line in lines:
            if line[0:9] == 'Satellite':
                if print_flag:
                    Remote_version_details = ','.join(Remote_version_details_list)
                    Fabric_links = ','.join(Fabric_links_list)
                    # print Fabric_links

                    satellites.append(Satellite(
                        satellite_id=Satellite_id,
                        device_name=Device_name,
                        type=Type,
                        state=State,
                        install_state=Install_state,
                        ip_address=Ip_address,
                        serial_number=Serial_number,
                        mac_address=Mac_address,
                        remote_version=Remote_version,
                        remote_version_details=Remote_version_details,
                        fabric_links=Fabric_links
                    ))

                # initialize satellite parameters
                Satellite_id = line[9:].strip()
                Device_name = ''
                Type = ''
                State = ''
                Install_state = ''
                Mac_address = ''
                Ip_address = ''
                Serial_number = ''
                Remote_version = ''
                Remote_version_details_list = []
                Fabric_links_list = []

                remote_version_flag = False
                fabric_links_flag = False
                print_flag = True
                continue

            if line[0:8] == '--------':
                continue

            if line[0:9] == '  Status:':
                status = line[10:].strip()
                if 'Connected' in status:
                    m = re.search('Connected \((.*)\)', status)
                    if m:
                        State = 'Connected'
                        Install_state = m.group(1)
                    else:
                        State = status
                else:
                    State = status
                continue

            if line[0:7] == '  Type:':
                Type = line[7:].strip()
                continue

            if line[0:24] == '  Displayed device name:':
                Device_name = line[24:].strip()
                continue

            if line[0:14] == '  MAC address:':
                Mac_address = line[14:].strip()
                continue

            if line[0:15] == '  IPv4 address:':
                subline = line[15:].strip()
                m = re.search('\d+\.\d+\.\d+\.\d+', subline)
                if m:
                    Ip_address = m.group(0)
                continue

            if line[0:16] == '  Serial Number:':
                Serial_number = line[16:].strip()
                continue

            if line[0:17] == '  Remote version:':
                Remote_version = line[17:].strip()
                remote_version_flag = True
                continue

            if remote_version_flag:
                if 'Received candidate fabric ports:' in line:
                    remote_version_flag = False
                elif 'Configured satellite fabric links:' in line:
                    remote_version_flag = False
                else:
                    subline = line.strip()
                    Remote_version_details_list.append(subline)
                    continue

            if 'Configured satellite fabric links:' in line:
                remote_version_flag = False
                fabric_links_flag = True
                continue

            if fabric_links_flag:
                if line[4] != ' ' and line[4] != '-':
                    subline = line.strip()
                    Fabric_links_list.append(subline)
                    continue

        Remote_version_details = ','.join(Remote_version_details_list)
        Fabric_links = ','.join(Fabric_links_list)
        # print Fabric_links

        satellites.append(Satellite(
            satellite_id=Satellite_id,
            device_name=Device_name,
            type=Type,
            state=State,
            install_state=Install_state,
            ip_address=Ip_address,
            serial_number=Serial_number,
            mac_address=Mac_address,
            remote_version=Remote_version,
            remote_version_details=Remote_version_details,
            fabric_links=Fabric_links
        ))

        ctx.host.satellites = satellites
