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
from models import ModulePackageState
from constants import PackageState
from base import BaseSoftwarePackageParser, BaseInventoryParser
from models import get_db_session_logger


class EXRSoftwarePackageParser(BaseSoftwarePackageParser):

    def set_host_packages_from_cli(self, ctx):
        admin_inactive_packages = {}
        admin_active_packages = {}
        admin_committed_packages = {}

        non_admin_inactive_packages = {}
        non_admin_active_packages = {}
        non_admin_committed_packages = {}

        inactive_packages = {}
        active_packages = {}
        committed_packages = {}
        host_packages = []

        cli_show_install_inactive = ctx.load_data('cli_show_install_inactive')
        cli_show_install_active = ctx.load_data('cli_show_install_active')
        cli_show_install_committed = ctx.load_data('cli_show_install_committed')

        cli_admin_show_install_inactive = ctx.load_data('cli_admin_show_install_inactive')
        cli_admin_show_install_active = ctx.load_data('cli_admin_show_install_active')
        cli_admin_show_install_committed = ctx.load_data('cli_admin_show_install_committed')

        # Handles Inactive Packages
        if isinstance(cli_admin_show_install_inactive, list):
            admin_inactive_packages = self.parse_inactive(cli_admin_show_install_inactive[0], PackageState.INACTIVE)

        if isinstance(cli_show_install_inactive, list):
            non_admin_inactive_packages = self.parse_inactive(cli_show_install_inactive[0], PackageState.INACTIVE)

        inactive_packages.update(admin_inactive_packages)
        inactive_packages.update(non_admin_inactive_packages)

        # Handles Active Packages
        if isinstance(cli_admin_show_install_active, list):
            admin_active_packages = self.parse_packages_by_node(cli_admin_show_install_active[0], PackageState.ACTIVE)

        if isinstance(cli_show_install_active, list):
            non_admin_active_packages = self.parse_packages_by_node(cli_show_install_active[0], PackageState.ACTIVE)

        active_packages.update(admin_active_packages)
        active_packages.update(non_admin_active_packages)

        # Handles Committed Packages
        if isinstance(cli_admin_show_install_committed, list):
            admin_committed_packages = self.parse_packages_by_node(cli_admin_show_install_committed[0],
                                                                   PackageState.ACTIVE_COMMITTED)

        if isinstance(cli_show_install_committed, list):
            non_admin_committed_packages = self.parse_packages_by_node(cli_show_install_committed[0],
                                                                       PackageState.ACTIVE_COMMITTED)

        committed_packages.update(admin_committed_packages)
        committed_packages.update(non_admin_committed_packages)

        if committed_packages:
            for package_name in active_packages:
                # Extracts the Package object
                active_package = active_packages.get(package_name)
                committed_package = committed_packages.get(package_name)
                if committed_package is not None:
                    # Peeks into the ModulePackageStates to see if the same line card
                    # with the same package appears in both active and committed areas.
                    for active_module_package_state in active_package.modules_package_state:
                        for committed_module_package_state in committed_package.modules_package_state:
                            if active_module_package_state.module_name == committed_module_package_state.module_name:
                                active_module_package_state.package_state = PackageState.ACTIVE_COMMITTED
                    active_package.state = PackageState.ACTIVE_COMMITTED

            for package_name in inactive_packages:
                # Extracts the Package object
                inactive_package = inactive_packages.get(package_name)
                committed_package = committed_packages.get(package_name)
                if committed_package is not None:
                    # Peeks into the ModulePackageStates to see if the same line card
                    # with the same package appears in both inactive and committed areas.
                    for inactive_module_package_state in inactive_package.modules_package_state:
                        for committed_module_package_state in committed_package.modules_package_state:
                            if inactive_module_package_state.module_name == committed_module_package_state.module_name:
                                inactive_module_package_state.package_state = PackageState.INACTIVE_COMMITTED
                    inactive_package.state = PackageState.INACTIVE_COMMITTED

        for package in active_packages.values():
            host_packages.append(package)

        for package in inactive_packages.values():
            host_packages.append(package)

        if len(host_packages) > 0:
            ctx.host.packages = host_packages
            return True

        return False

    def parse_inactive(self, lines, package_state):
        """
        NON-ADMIN:
        RP/0/RP0/CPU0:Deploy#show install inactive
        5 inactive package(s) found:
            ncs6k-k9sec-5.2.5.47I
            ncs6k-mpls-5.2.5.47I
            ncs6k-5.2.5.47I.CSCuy47880-0.0.4.i
            ncs6k-mgbl-5.2.5.47I
            ncs6k-5.2.5.CSCuz65240-1.0.0

        ADMIN: Inactive
        sysadmin-vm:0_RP0:NCS-Deploy2# show install inactive
        Wed Jun  8  23:03:38.637 UTC
         Node 0/RP0 [RP]
            Inactive Packages:
               ncs6k-sysadmin-5.0.1.CSCun50237-1.0.0
               ncs6k-sysadmin-5.2.3.CSCut94440-1.0.0
               ncs6k-sysadmin-5.0.1.CSCum80946-1.0.0
               ncs6k-sysadmin-5.0.1.CSCus71815-1.0.0
               ncs6k-sysadmin-5.2.3.CSCut24295-1.0.0
               ncs6k-sysadmin-5.0.1.CSCuq00795-1.0.0
         Node 0/RP1 [RP]
            Inactive Packages:
               ncs6k-sysadmin-5.0.1.CSCun50237-1.0.0
               ncs6k-sysadmin-5.2.3.CSCut94440-1.0.0
               ncs6k-sysadmin-5.0.1.CSCum80946-1.0.0
               ncs6k-sysadmin-5.0.1.CSCus71815-1.0.0
               ncs6k-sysadmin-5.2.3.CSCut24295-1.0.0
               ncs6k-sysadmin-5.0.1.CSCuq00795-1.0.0
        """
        package_dict = {}
        if lines:
            lines = lines.splitlines()
            for line in lines:
                line = line.strip()
                if len(line) == 0: continue

                if re.match("(ncs.*|asr9k.*)", line):
                    package_dict[line] = Package(location=None, name=line, state=package_state)

        return package_dict

    def parse_packages_by_node(self, lines, package_state):
        """
        Used to parse 'show install active/committed' CLI output.
        Package
            ModulePackageState
            ModulePackageState

        NON-ADMIN: Active
        RP/0/RP0/CPU0:Deploy#show install active
        Node 0/RP0/CPU0 [RP]
            Boot Partition: xr_lv0
            Active Packages: 8
                ncs6k-xr-5.2.5 version=5.2.5 [Boot image]
                ncs6k-mgbl-5.2.5
                ncs6k-mcast-5.2.5
                ncs6k-li-5.2.5
                ncs6k-k9sec-5.2.5
                ncs6k-doc-5.2.5
                ncs6k-mpls-5.2.5
                ncs6k-5.2.5.CSCux82987-1.0.0

        Node 0/RP1/CPU0 [RP]
            Boot Partition: xr_lv0
            Active Packages: 8
                ncs6k-xr-5.2.5 version=5.2.5 [Boot image]
                ncs6k-mgbl-5.2.5
                ncs6k-mcast-5.2.5
                ncs6k-li-5.2.5
                ncs6k-k9sec-5.2.5
                ncs6k-doc-5.2.5
                ncs6k-mpls-5.2.5
                ncs6k-5.2.5.CSCux82987-1.0.0

        ADMIN: Active
        sysadmin-vm:0_RP0:NCS-Deploy2# show install active
        Wed Jun  8  22:47:32.908 UTC
         Node 0/RP0 [RP]
            Active Packages: 2
               ncs6k-sysadmin-5.2.5 version=5.2.5 [Boot image]
               ncs6k-sysadmin-5.2.5.CSCuy44658-1.0.0

         Node 0/RP1 [RP]
            Active Packages: 2
               ncs6k-sysadmin-5.2.5 version=5.2.5 [Boot image]
               ncs6k-sysadmin-5.2.5.CSCuy44658-1.0.0

         Node 0/2 [LC]
            Active Packages: 2
               ncs6k-sysadmin-5.2.5 version=5.2.5 [Boot image]
               ncs6k-sysadmin-5.2.5.CSCuy44658-1.0.0

        """
        package_dict = {}

        if lines:
            trunks = self.get_trunks(lines.splitlines())
            if len(trunks) > 0:
                # Collect all the packages
                package_list = []
                for module in trunks:
                    for package in trunks[module]:
                        if not package in package_list and re.match("(ncs.*|asr9k.*|iosxr.*)", package):
                            package_list.append(package)

                for package_name in package_list:
                    package = Package(
                        name=package_name,
                        location=None,
                        state=package_state)

                    # Check which module has this package
                    for module in trunks:
                        for line in trunks[module]:
                            if line == package_name:
                                package.modules_package_state.append(ModulePackageState(
                                    module_name=module,
                                    package_state=package_state))

                    package_dict[package_name] = package

        return package_dict

    def get_trunks(self, lines):
        """
        Return the CLI outputs in trunks.  Each Trunk is a section of module and its packages.
        Below is an example of two trunks.

        Node 0/RP0/CPU0 [RP]
            Boot Partition: xr_lv36
            Active Packages: 7
                ncs6k-xr-5.2.1 version=5.2.1 [Boot image]
                ncs6k-doc-5.2.1
                ncs6k-k9sec-5.2.1
                ncs6k-mcast-5.2.1
                ncs6k-mgbl-5.2.1
                ncs6k-mpls-5.2.1
                ncs6k-5.2.1.CSCur01489-1.0.0

        Node 0/RP1/CPU0 [RP]
            Boot Partition: xr_lv36
            Active Packages: 7
                ncs6k-xr-5.2.1 version=5.2.1 [Boot image]
                ncs6k-doc-5.2.1
                ncs6k-k9sec-5.2.1
                ncs6k-mcast-5.2.1
                ncs6k-mgbl-5.2.1
                ncs6k-mpls-5.2.1
                ncs6k-5.2.1.CSCur01489-1.0.0
        """
        trunks = {}
        trunk = []
        module = None

        for line in lines:
            line = line.strip()
            if len(line) == 0: continue

            m = re.match("(Node.*)", line)
            if m:
                if module is not None:
                    trunks[module] = trunk

                trunk = []
                # Node 0/RP0/CPU0 [RP] becomes 0/RP0/CPU0
                module = line.split()[1]

                # For admin, CPU0 is missing for the node
                if 'CPU0' not in module:
                    module = '{}/CPU0'.format(module)
            else:
                if module is not None:
                    if re.match("(ncs.*|asr9k.*)", line):
                        # For situation: ncs6k-xr-5.2.1 version=5.2.1 [Boot image]
                        trunk.append(line.split()[0])
                    else:
                        trunk.append(line)

        if module is not None:
            trunks[module] = trunk

        return trunks


class EXRInventoryParser(BaseInventoryParser):

    def process_inventory(self, ctx):
        """
        For ASR9K-64, NCS6K and NCS5500
        There is only one chassis in this case. It most likely shows up first in the
        output of "admin show inventory".
        Example for ASR9K-64:
        Name: Rack 0                Descr: ASR-9904 AC Chassis
        PID: ASR-9904-AC            VID: V01                   SN: FOX1746GHJ9

        Example for NCS6K:
        Name: Rack 0                Descr: NCS 6008 - 8-Slot Chassis
        PID: NCS-6008               VID: V01                   SN: FLM17476JWA

        Example for NCS5500:
        Name: Rack 0                Descr: NCS5500 8 Slot Single Chassis
        PID: NCS-5508               VID: V01                   SN: FGE194714QX

        """
        if not ctx.load_data('cli_show_inventory'):
            return
        inventory_output = ctx.load_data('cli_show_inventory')[0]

        inventory_data = self.parse_inventory_output(inventory_output)

        for i in xrange(0, len(inventory_data)):
            if "Chassis" in inventory_data[i]['description']:
                return self.store_inventory(ctx, inventory_data, i)

        logger = get_db_session_logger(ctx.db_session)
        logger.exception('Failed to find chassis in inventory output for host {}.'.format(ctx.host.hostname))
        return


class NCS1K5KInventoryParser(EXRInventoryParser):

    def process_inventory(self, ctx):
        """
        For NCS1K and NCS5K.
        There is only one chassis in this case. It most likely shows up first in the
        output of "admin show inventory".
        Example for NCS1K:
        Name: Rack 0                Descr: Network Convergence System 1000 Controller
        PID: NCS1002                VID: V01                   SN: CHANGE-ME-

        Example for NCS5K:
        Name: Rack 0                Descr:
        PID: NCS-5002               VID: V01                   SN: FOC1946R0DH
        """
        if not ctx.load_data('cli_show_inventory'):
            return
        inventory_output = ctx.load_data('cli_show_inventory')[0]

        inventory_data = self.parse_inventory_output(inventory_output)

        for i in xrange(0, len(inventory_data)):
            if "Rack 0" in inventory_data[i]['name']:
                return self.store_inventory(ctx, inventory_data, i)

        logger = get_db_session_logger(ctx.db_session)
        logger.exception('Failed to find chassis in inventory output for host {}.'.format(ctx.host.hostname))
        return

