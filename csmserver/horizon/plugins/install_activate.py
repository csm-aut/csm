# =============================================================================
# Copyright (c)  2016, Cisco Systems
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

from horizon.plugin import Plugin
from horizon.plugin_lib import clear_cfg_inconsistency, install_activate_deactivate
import horizon.package_lib as package_lib


class InstallActivatePlugin(Plugin):
    """
    A plugin for install activate operation
    """
    @staticmethod
    def _get_tobe_activated_pkg_list(manager, device):
        """
           Get list of package which can be activated.
        """
        try:
            packages = manager.csm.software_packages
        except AttributeError:
            manager.error("No packages selected")

        added_pkgs = package_lib.NewPackage(packages)
        installed_inact = device.send("admin show install inactive summary")
        installed_act = device.send("admin show install active summary")

        inactive_pkgs = package_lib.OnboxPackage(installed_inact, "Inactive Packages")
        active_pkgs = package_lib.OnboxPackage(installed_act, "Active Packages")

        # Skip operation if to be activated packages are already active
        package_to_activate = package_lib.extra_pkgs(active_pkgs.pkg_list, added_pkgs.pkg_list)

        if package_to_activate:
            # Test If there is anything added but not inactive
            pkg_to_activate = package_lib.package_intersection(
                added_pkgs.pkg_list, inactive_pkgs.pkg_list)
            if not pkg_to_activate:
                # "explicit is better than implicit" being one of the mottos in "The Zen of Python"
                to_activate = " ".join(map(str, added_pkgs.pkg_list))
                state_of_packages = "\nTo activate :{} \nInactive: {} \nActive: {}".format(
                    to_activate, installed_inact, installed_act
                )
                manager.log(state_of_packages)
                manager.error('To be activated package is not in inactive packages list')
            else:
                return " ".join(pkg_to_activate)

    @staticmethod
    def start(manager, device, *args, **kwargs):
        """
        Performs install activate operation
        """
        clear_cfg_inconsistency(manager, device)

        operation_id = None
        csm_ctx = device.get_property('ctx')
        if csm_ctx:
            if hasattr(csm_ctx, 'operation_id'):
                operation_id = csm_ctx.operation_id

        if operation_id is None or operation_id == -1:
            tobe_activated = InstallActivatePlugin._get_tobe_activated_pkg_list(manager, device)
            if not tobe_activated:
                manager.log("The packages are already active, nothing to be activated.")
                return True

        if operation_id is not None and operation_id != -1:
            cmd = 'admin install activate id {} prompt-level none async'.format(operation_id)
        else:
            cmd = 'admin install activate {} prompt-level none async'.format(tobe_activated)

        manager.log("Activate Package(s) Pending")
        install_activate_deactivate(manager, device, cmd)
        manager.log("Activate Package(s) Done")