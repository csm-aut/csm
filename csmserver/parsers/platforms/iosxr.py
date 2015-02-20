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
            
            # Derive the software platform and release from the active packages
            self.set_platform_and_release(host, active_packages)
        
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

    def set_platform_and_release(self, host, packages):
        if packages is not None:
            for package in packages.values():
                if 'mini' in package.name:
                    tokens = package.name.split('-')
                    # ['asr9k', 'mini', 'px', '4.3.1']
                    if len(tokens) == 4:
                        host.software_platform = tokens[0] + '-' + tokens[2]
                        host.software_version = tokens[3]
        
    def parseContents(self, lines, package_state):
        packages_dict = {}

        if lines is None:
            return packages_dict

        found = False
        lines = lines.splitlines()

        for line in lines:
            if found:
                line = line.strip()

                if (':' in line):
                    location, name = line.split(':')
                else:
                    location = ''
                    name = line

                #skip anything after the blank line
                if len(line) == 0:
                    break
                
                package = Package(location = location, name = name, state = package_state)
                packages_dict[name] = package

            elif 'Packages' in line:
                found = True

        return packages_dict
