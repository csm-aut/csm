# =============================================================================
# install_add.py - plugin for adding packages
#
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
from horizon.plugin_lib import install_add_remove


class InstallAddPlugin(Plugin):
    """
    A plugin for add operation
    it will create xml equivalent for
    add operation. 
    Arguments:
    1.one argument of type dictionary
    """
    @staticmethod
    def start(manager, device, *args, **kwargs):
        """
        It performs add operation of the pies listed in given file
        """
        server_repository_url = None
        try:
            server_repository_url = manager.csm.server_repository_url
        except AttributeError:
            pass

        if server_repository_url is None:
            manager.error("No repository provided")

        try:
            packages = manager.csm.software_packages
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
            if device.family == "ASR9K" and ".pie" in package:
                v_packages.append(package)
                continue
            if device.family == "NCS6K" and ".pkg" in package:
                v_packages.append(package)
                continue
            if device.family == "NCS6K" and ".smu" in package:
                v_packages.append(package)
                continue

        s_packages = " ".join(v_packages)
        if device.family == "ASR9K":
            cmd = "admin install add source {} {} async".format(server_repository_url, s_packages)
        else:
            cmd = "install add source {} {} ".format(server_repository_url, s_packages)

        manager.log("Add Package(s) Pending")
        install_add_remove(manager, device, cmd, has_tar=has_tar)
        manager.log("Package(s) Added Successfully")