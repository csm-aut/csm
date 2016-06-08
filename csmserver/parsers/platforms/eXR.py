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
from models import Package
from models import ModulePackageState
from constants import PackageState
from parsers.base import BasePackageParser

import re


class CLIPackageParser(BasePackageParser):
    def get_packages_from_cli(self, ctx):
        inactive_packages = {}
        active_packages = {}
        committed_packages = {}
        host_packages = []

        cli_show_install_inactive = ctx.load_data('cli_show_install_inactive')
        cli_show_install_active = ctx.load_data('cli_show_install_active')
        cli_show_install_committed = ctx.load_data('cli_show_install_committed')

        if isinstance(cli_show_install_inactive, list):
            inactive_packages = self.parse_inactive(cli_show_install_inactive[0], PackageState.INACTIVE)

        if isinstance(cli_show_install_active, list):
            active_packages = self.parse_active_and_committed(cli_show_install_active[0], PackageState.ACTIVE)

        if isinstance(cli_show_install_committed, list):
            committed_packages = self.parse_active_and_committed(cli_show_install_committed[0], PackageState.ACTIVE_COMMITTED)

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

    """
    Used to parse 'show install inactive' CLI output.

    19 inactive package(s) found:
        ncs6k-mcast-5.0.1
        ncs6k-mgbl-5.0.1
        ncs6k-mpls-5.0.1
        ncs6k-k9sec-5.0.1
        ncs6k-xr-5.0.1
        ncs6k-doc-5.0.1
    """
    def parse_inactive(self, lines, package_state):
        package_dict = {}

        if lines is None:
            return package_dict

        found = False
        lines = lines.splitlines()

        for line in lines:
            if found:
                location = None
                name = line.strip()

                # Skip anything after the blank line
                if len(name) == 0:
                    break

                package = Package(location=location, name=name, state=package_state)
                package_dict[name] = package

            elif 'package' in line:
                found = True

        return package_dict

    """
    Used to parse 'show install active/committed' CLI output.
        Package
            ModulePackageState
            ModulePackageState
    """
    def parse_active_and_committed(self, lines, package_state):
        package_dict = {}

        if lines is None:
            return package_dict

        lines = lines.splitlines()
        trunks = self.get_trunks(lines)
        if len(trunks) > 0:
            # Collect all the packages
            package_list = []
            for module in trunks:
                for package in trunks[module]:
                    if not package in package_list and re.match("(ncs.*|asr9k.*)", package):
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
    def get_trunks(self, cli_output):
        trunks = {}
        trunk = []
        module = None

        for line in cli_output:
            line = line.strip()
            if len(line) == 0: continue

            m = re.match("(Node.*)", line)
            if m:
                if module is not None:
                    trunks[module] = trunk

                trunk = []
                # Node 0/RP1/CPU0 [RP]
                module = line.split()[1]
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
