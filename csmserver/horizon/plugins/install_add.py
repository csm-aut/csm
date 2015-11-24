# =============================================================================
# install_add.py - plugin for adding packages
#
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
from ..plugin_lib import watch_operation, get_package


class InstallAddPlugin(IPlugin):
    """
    A plugin for add operation
    it will create xml equivalent for
    add operation. 
    Arguments:
    1.one argument of type dictionary
    """
    NAME = "INSTALL_ADD"
    DESCRIPTION = "Install Add Packages"
    TYPE = "ADD"
    VERSION = "1.0.0"
    FAMILY = ["ASR9K"]

    @staticmethod
    def start(manager, device, *args, **kwargs):
        """
        It performs add operation of the pies listed in given file
        """
        error_str = "Error:  "
        ctx = device.get_property("ctx")

        server_repository_url = None
        try:
            server_repository_url = ctx.server_repository_url
        except AttributeError:
            pass

        if server_repository_url is None:
            manager.error("No repository not provided")

        try:
            packages = ctx.software_packages
        except AttributeError:
            manager.error("No package list provided")

        # if kwargs.get('turbo_boot',None) and not pkg_name_list :
        #     # It's okay to have package list empty in case of TB as just vm is used for TB
        #     # This is not treated as  failure
        #     return True
        #

        has_tar = False
        v_packages = []
        for package in packages:
            if ".vm-" in package:
                continue
            if ".tar" in package:
                has_tar = True
                v_packages.append(package)
                continue
            if ".pie" in package:
                v_packages.append(package)
                continue

        s_packages = " ".join(v_packages)

        cmd = "admin install add source {} {} async".format(server_repository_url, s_packages)
        output = device.send(cmd, timeout=7200)
        result = re.search('Install operation (\d+) \'', output)
        if result:
            op_id = result.group(1)
            if hasattr(ctx, 'operation_id'):
                if has_tar is True:
                    ctx.operation_id = op_id
                    manager.log("The operation {} stored".format(op_id))
        else:
            manager.log_install_errors(output)
            manager.error("Operation failed.")

        if error_str not in output:
            output = watch_operation(manager, device, op_id)
            if re.search("Install operation (\d+) failed", output):
                manager.error(output)
        else:
            manager.log_install_errors(output)
            manager.error("Operation {} failed".format(op_id))

        manager.log("Operation {} succeeded.".format(op_id))
        get_package(device)
