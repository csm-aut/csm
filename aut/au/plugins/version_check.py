# =============================================================================
# version_check.py - Plugin for checking version of running
#
# Copyright (c)  2013, Cisco Systems
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


from au.lib.global_constants import *

from au.plugins.plugin import IPlugin

import re


class SoftwareVersionPlugin(IPlugin):

    """
    ASR9k Pre-upgrade check
    This plugin checks if version of all inputs packages are same.
    If input package contains SMUs only , ensure that box is running same ver.
    """
    NAME = "SOFTWARE_VERSION"
    DESCRIPTION = "Software Version Check"
    TYPE = "PRE_UPGRADE"
    VERSION = "0.1.1"

    def start(self, device, *args, **kwargs):
        """
        """

        if device:
            success, output = device.execute_command("show version brief")
            if success:
                match = re.search('Version (\d+\.\d+\.\d+)', output)
                if match:
                    version = match.group(1)
                    device.store_property('version', version)
                    self.log(
                        "Device {} version detected: {}".format(
                            device.name, version)
                    )
                match = re.search(
                    'Version (\d+\.\d+\.\d+\.\d+[a-zA-Z])', output)
                if match:
                    version = match.group(1)
                    device.store_property('version', version)
                    self.log(
                        "Device {} version detected: {}".format(
                            device.name, version)
                    )
                match = re.search('cisco (\w+)', output)
                if match:
                    platform = match.group(1).lower()
                    device.store_property('platform', platform)
                    self.log(
                        "Device {} platform detected: {}".format(
                            device.name,
                            platform
                        )
                    )
                    return

        self.error(
            "Can not determine device version for {}".format(device.name)
        )
