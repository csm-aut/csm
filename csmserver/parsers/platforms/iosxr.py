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

"""
The default CLI package parser for IOS-XR.
"""
class BaseCLIPackageParser(object):
        
    def get_packages_from_cli(self, host, install_inactive_cli=None, install_active_cli=None, install_committed_cli=None):        
        inactive_packages = {}
        active_packages = {}
        committed_packages = {}
        host_packages = []
        
        if install_inactive_cli is not None:
            inactive_packages = self.parseContents(install_inactive_cli, PackageState.INACTIVE)
        
        if install_active_cli is not None:
            active_packages = self.parseContents(install_active_cli, PackageState.ACTIVE)
        
        if install_committed_cli is not None:
            committed_packages = self.parseContents(install_committed_cli, PackageState.ACTIVE_COMMITTED)                               
        
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
            host.packages = host_packages
            return True
        
        return False
        
    def parseContents(self, lines, package_state):
        packages_dict = {}

        if lines is None:
            return packages_dict

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
                
                package = Package(location = location, name = name, state = package_state)
                packages_dict[name] = package

            elif 'Packages' in line:
                found = True

        return packages_dict
