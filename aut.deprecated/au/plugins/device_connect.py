# =============================================================================
# device_connect.py - Plugin for checking version of running
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
from au.device import DeviceError
from au.plugins.package_state import get_package

import re


class DeviceConnectPlugin(IPlugin):

    """
    This is a plugin maintaining the initial device connection
    """
    NAME = "CONNECTION"
    DESCRIPTION = "Device Connection Check"
    TYPE = "PRE_UPGRADE"
    VERSION = "0.1.0"

    def start(self, device, *args, **kwargs):
        """
        """
        success = None
        try:
            success = device.connect()
        except DeviceError:
            print("Device Error: {}".format(device.error_code))

        if success:
            device.log_event(
                "Device {} connected successfully.".format(device.name)
            )

            err_msg = get_package(device)

            if err_msg:
                self.error(err_msg)

            return True

        self.error(
            "Can not connect to device {}".format(device.name)
        )
