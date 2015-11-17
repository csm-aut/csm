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

import re
from plugin import IPlugin

from plugin_lib import get_package, watch_operation
import pkg_utils



class InstallRemovePlugin(IPlugin):

    """
    A plugin for install remove operation
    """
    NAME = "INSTALL_REMOVE"
    DESCRIPTION = "Install Remove Packages"
    TYPE = "REMOVE"
    VERSION = "1.0.0"
    FAMILY = ["ASR9K"]

    @staticmethod
    def start(manager, device, *args, **kwargs):
        """
        Performs install remove operation
        """
        SMU_RE = r'CSC\D\D\d\d\d'
        FP_RE = r'fp\d+'
        SP_RE = r'sp\d+'

        ctx = device.get_property("ctx")

        try:
            packages = ctx.software_packages
        except AttributeError:
            manager.error("No package list provided")

        deact_pkgs = pkg_utils.NewPackage(packages)
        installed_inact = device.send("admin show install inactive summary")
        inactive_pkgs = pkg_utils.OnboxPackage(installed_inact, "Inactive Packages")

        packages_to_remove = pkg_utils.package_intersection(deact_pkgs.pkg_list, inactive_pkgs.pkg_list)
        if not packages_to_remove:
            manager.log("Packages already removed. Nothing to be removed")
            get_package(device)
            return True

        to_remove = " ".join(packages_to_remove)

        op_success = "The install operation will continue asynchronously"

        cmd = 'admin install remove {} prompt-level none async'.format(to_remove)

        manager.log("Remove Package(s) Pending")
        output = device.send(cmd, timeout=7200)
        if op_success in output:
            result = re.search('Install operation (\d+) \'', output)
            if result:
                op_id = result.group(1)
                manager.log("Waiting to finish operation: {}".format(op_id))
                watch_operation(manager, device, op_id)
                get_package(device)
                return True
            else:
                manager.error("Operation ID not found")
        else:
            manager.error("Operation failed")
