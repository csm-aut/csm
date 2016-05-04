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
from constants import PackageState
from parsers.base import BasePackageParser

import re

"""
CLI package parser for NX-OS.
"""
class CLIPackageParser(BasePackageParser):

    def get_packages_from_cli(self, host, install_inactive_cli=None, install_active_cli=None, install_committed_cli=None):
        host_packages = []

        if install_committed_cli is not None:
            # Should have only one committed package
            committed_packages = self.get_committed_packages(install_committed_cli, PackageState.ACTIVE_COMMITTED)
            if committed_packages:
                for package in committed_packages:
                    host_packages.append(package)

        if install_inactive_cli is not None:
            inactive_packages = self.get_inactive_packages(install_inactive_cli, PackageState.INACTIVE)
            if inactive_packages:
                for package in inactive_packages:
                    host_packages.append(package)

        if len(host_packages) > 0:
            host.packages = host_packages
            return True

        return False

    def get_inactive_packages(self, lines, package_state):
        """
        lines contains the CLI outputs for 'sh install inactive'
        """
        packages = []

        lines = lines.splitlines()
        for line in lines:
            if 'lib32_n9000' in line:
                match = re.search(r'\S*lib32_n9000', line)
                if match:
                    package_name = match.group()
                    packages.append(Package(location=None, name=package_name, state=package_state))

        return packages

    def get_committed_packages(self, lines, package_state):
        """
        lines contains the CLI outputs for 'sh install packages | grep lib32_n9000'

        bfd.lib32_n9000                         2.0.0-7.0.3.I4.1              installed
        core.lib32_n9000                        2.0.0-7.0.3.I4.1              installed
        eigrp.lib32_n9000                       2.0.0-7.0.3.I4.1              installed
        eth.lib32_n9000                         2.0.0-7.0.3.I4.1              installed
        """
        packages = []
        lines = lines.splitlines()
        for line in lines:
            if 'lib32_n9000' in line:
                match = re.search(r'\S*lib32_n9000', line)
                if match:
                    package_name = match.group()
                    packages.append(Package(location=None, name=package_name, state=package_state))

        return packages
