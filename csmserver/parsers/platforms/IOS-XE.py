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
import logging

"""
CLI package parser for IOS-XE.
"""
class CLIPackageParser(BasePackageParser):
        
    def get_packages_from_cli(self, ctx):
        host_packages = []
        committed_packages = {}

        cli_show_install_inactive = ctx.load_data('cli_show_install_inactive')
        cli_show_install_committed = ctx.load_data('cli_show_install_committed')

        if isinstance(cli_show_install_committed, list):
            # Should have only one committed package
            committed_packages = self.get_committed_packages(cli_show_install_committed[0], PackageState.ACTIVE_COMMITTED)
            if committed_packages:
                for package in committed_packages.values():
                    logging.warning('package = %s', package)
                    host_packages.append(package)

        if isinstance(cli_show_install_inactive, list):
            inactive_packages = self.get_inactive_packages(cli_show_install_inactive[0], PackageState.INACTIVE)
            if inactive_packages:
                for package in inactive_packages:
                    host_packages.append(package)

        if len(host_packages) > 0:
            ctx.host.packages = host_packages
            return True
        
        return False

    def get_inactive_packages(self, lines, package_state):
        """
        lines contains the CLI outputs for 'cd bootflash:', then 'dir'
        """
        packages = []

        lines = lines.splitlines()
        for line in lines:
            if '.bin' in line:
                match = re.search(r'asr\S*', line)
                if match:
                    package_name = match.group()
                    packages.append(Package(location=None, name=package_name, state=package_state))

        return packages

    def get_committed_packages(self, lines, package_state):
        """
        lines contains the CLI outputs for 'show version running'
        """
        package_dict = {}

        if lines:
            trunks = self.get_trunks(lines.splitlines())
            if len(trunks) > 0:
                # Collect all the packages
                package_list = []
                for module in trunks:
                    for package in trunks[module]:
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

          File: consolidated:packages.conf, on: RP0
          File: consolidated:asr920-rpbase.03.16.00.S.155-3.S-ext.pkg, on: RP0
          File: consolidated:asr920-rpcontrol.03.16.00.S.155-3.S-ext.pkg, on: RP0/0
          File: consolidated:asr920-rpios-universalk9_npe.03.16.00.S.155-3.S-ext.pkg, on: RP0/0
          File: consolidated:asr920-rpaccess.03.16.00.S.155-3.S-ext.pkg, on: RP0/0

        RP0
            packages.conf
            asr920-rpbase.03.16.00.S.155-3.S-ext.pkg
        RP0/0
            asr920-rpcontrol.03.16.00.S.155-3.S-ext.pkg
            asr920-rpios-universalk9_npe.03.16.00.S.155-3.S-ext.pkg
            asr920-rpaccess.03.16.00.S.155-3.S-ext.pkg

        """
        trunks = {}
        module = None

        for line in lines:
            line = line.strip()
            if len(line) == 0: continue

            m = re.search(r'.*(packages.conf).*on: (.*)', line) or re.search(r'.*(asr9.*pkg).*on: (.*)', line)
            if m:
                module = m.group(2)
                trunk = m.group(1)
                if module not in trunks.keys():
                    pkg = []
                else:
                    pkg = trunks[module]

                pkg.append(trunk)
                trunks[module] = pkg

                logging.warning('module = %s, pkg = %s', module, pkg)

        return trunks
