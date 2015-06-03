# =============================================================================
# Copyright (c)  2013, Cisco Systems
# All rights reserved.
#
# Author: Suryakant Kewat
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

from au.lib.parser import parsecli

from sys import stdout
import time
from au.lib.global_constants import *
from au.plugins.plugin import IPlugin
import au.lib.pkg_utils as pkgutils
from au.plugins.package_state import get_package


class InstallRemovePlugin(IPlugin):

    """
    A plugin for install remove operation
    """
    NAME = "INSTALL_REMOVE"
    DESCRIPTION = "Install Remove Packages"
    TYPE = "REMOVE"
    VERSION = "0.0.1"

    def _watch_operation(self, device, oper_id):
        """
        Method to keep watch on progress of install remove operation.
        If the operation was process rseatrts , return immediately , if
        reload was needed, wait till reload completes and all nodes are
        in state or timeout.

        """
        no_oper = r'There are no install requests in operation'
        in_oper = r'The operation is (\d+)% complete'
        success_oper = r'Install operation (\d+) completed successfully'
        completed_with_failure = 'Install operation (\d+) completed with failure'
        failed_oper = r'Install operation (\d+) failed'
        # restart = r'Parallel Process Restart'
        reload = r'Parallel Reload'
        install_method = r'Install method: (.*)'
        cmd = "admin show install request"

        stdout.write("\n\r")
        while 1:
            time.sleep(5)
            success, output = device.execute_command(cmd)
            if success and no_oper in output:
                # Operation completed
                break
            elif success and re.search(in_oper, output):
                # Print banner and continue
                progress = re.search(
                    'The operation is (\d+)% complete', output).group(0)
                stdout.write("%s \r" % (progress))
                stdout.flush()
                continue

        # Ensure operation success and get restart type
        cmd = "admin show install log %d detail" % int(oper_id)
        success, output = device.execute_command(cmd)

        if not success or re.search(failed_oper, output):
            self.error(output)


        return True

    def _wait_for_reload(self, device):
        """
         Wait for system to come up with max timeout as 10 Minutes

        """
        status = device.reconnect()
        # Connection to device failed
        if not status :
            return status

        # Connection to device is stablished , now look for all nodes to xr run state
        timeout = 450
        poll_time = 30
        time_waited = 0
        xr_run = "IOS XR RUN"

        success = False
        cmd = "admin show platform"
        print "Waiting all nodes to come up"
        time.sleep(100)
        while 1:
            # Wait till all nodes are in XR run state
            time_waited += poll_time
            if time_waited >= timeout:
                break
            time.sleep(poll_time)
            success, output = device.execute_command(cmd)
            if success and xr_run in output:
                inventory = pkgutils.parse_xr_show_platform(output)
                if pkgutils.validate_xr_node_state(inventory, device):
                    return True

        # Some nodes did not come to run state
        return False

    def _get_active_pkgs(self, device):
        """
            Get Active package on the device
        """

        cmd = "admin show install active summary"
        success, output = device.execute_command(cmd)
        if success:
            return output
        else:
            self.error("Failed : %s \n %s" % (cmd, output))

    def _get_inactive_pkgs(self, device):
        """
            Get InActive package on the device
        """
        cmd = "admin show install inactive summary"
        success, output = device.execute_command(cmd)
        if success:
            return output
        else:
            self.error("Failed : %s \n %s" % (cmd, output))

    def _get_tobe_activated_pkglist(self, device, kwargs):
        """
           Get list of package which can be activated.
        """

        pkg_list = kwargs.get('pkg_file', None)
        added_pkgs = pkgutils.NewPackage(pkg_list)

        installed_inact = self._get_inactive_pkgs(device)
        installed_act = self._get_active_pkgs(device)
        inactive_pkgs = pkgutils.OnboxPackage(
            installed_inact, "Inactive Packages")
        active_pkgs = pkgutils.OnboxPackage(installed_act, "Active Packages")

        # Skip operation if to be activated packages are already active
        package_to_activate = pkgutils.extra_pkgs(
            active_pkgs.pkg_list, added_pkgs.pkg_list)

        if package_to_activate:
            # Test If there is anything added but not inactive
            pkg_to_activate = pkgutils.pkg_tobe_activated(
                added_pkgs.pkg_list, inactive_pkgs.pkg_list, active_pkgs.pkg_list
            )
            if not pkg_to_activate:
                to_activate = " ".join(added_pkgs.pkg_named_list)
                state_of_packages = "To activate :{} \nInactive: {} \nActive: {}".format(
                    to_activate, installed_inact, installed_act
                )
                self.log(state_of_packages)
                self.error(
                    'To be activated package is not in inactive packages list')
            else:
                return " ".join(pkg_to_activate)

    def _install_remove(self, device, kwargs):
        """
        Performs install remove operation
        """
        SMU_RE = r'CSC\D\D\d\d\d'
        FP_RE = r'fp\d+'
        SP_RE = r'sp\d+'
        tobe_deactivated = []
        pkg_list = kwargs.get('pkg_file', None)
        deact_pkg = pkgutils.NewPackage(pkg_list)
        for pk2 in deact_pkg.pkg_list:
            pk2.partition="disk0"
            if re.match(SMU_RE, pk2.pkg) or re.match(FP_RE, pk2.pkg) or \
                  re.match(SP_RE, pk2.pkg):
                if pk2.arch:
                    pkg = "%s:%s-%s-%s.%s-%s" % (
                      pk2.partition, pk2.platform, pk2.arch,
                      pk2.version, pk2.pkg, pk2.format
                    )
                else:
                    pkg = "%s:%s-%s.%s-%s" % (
                      pk2.partition, pk2.platform,
                      pk2.version, pk2.pkg, pk2.format
                    )

            else:
                if pk2.arch:
                    pkg = "%s:%s-%s-%s-%s" % (
                      pk2.partition, pk2.platform, pk2.pkg, pk2.arch,
                      pk2.version
                    )
                else:
                    pkg = "%s:%s-%s-%s" % (
                      pk2.partition, pk2.platform, pk2.pkg, 
                      pk2.version
                    )

            tobe_deactivated.append(pkg)
        to_deactivate=" ".join( tobe_deactivated)
        deact_list = to_deactivate

        op_success = "The install operation will continue asynchronously"

        cmd = 'admin install remove {} prompt-level none async'.format(
            deact_list)
        success, output = device.execute_command(cmd)
        if success and op_success in output:
            op_id = re.search('Install operation (\d+) \'', output).group(1)
            self._watch_operation(device, op_id)
            get_package(device)
            return True
        else:
            self.error('{} \n {}'.format(cmd, output))

    def start(self, device, *args, **kwargs):
        """
        Start the plugin
        Return False if the plugin has found an error, True otherwise.
        """
        self._install_remove(device, kwargs)
