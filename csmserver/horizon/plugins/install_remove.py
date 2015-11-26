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
from ..plugin_lib import get_package, install_add_remove
import horizon.package_lib as package_lib


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
        ctx = device.get_property("ctx")

        try:
            packages = ctx.software_packages
        except AttributeError:
            manager.error("No package list provided")

        deact_pkgs = package_lib.NewPackage(packages)
        installed_inact = device.send("admin show install inactive summary")
        inactive_pkgs = package_lib.OnboxPackage(installed_inact, "Inactive Packages")

        packages_to_remove = package_lib.package_intersection(deact_pkgs.pkg_list, inactive_pkgs.pkg_list)
        if not packages_to_remove:
            manager.warning("Packages already removed. Nothing to be removed")
            get_package(device)
            return True

        to_remove = " ".join(packages_to_remove)

        cmd = 'admin install remove {} prompt-level none async'.format(to_remove)

        manager.log("Remove Package(s) Pending")
        install_add_remove(manager, device, cmd)
        manager.log("Package(s) Removed Successfully")