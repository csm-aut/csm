#==============================================================
# isis_unsetoverload.py  - Plugin for setting isis set-overload bit
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


from au.plugins import IPlugin
import re
#import condor


class isisunSetOverloadPostPlugin(IPlugin):

    """
    XR Post-upgrade check
    This plugin removes set-overload-bit on all isis instance
    """
    NAME = "ISIS_UNSET_OVERLOAD_BIT_POST"
    DESCRIPTION = "ISIS unset overload bit postcheck "
    TYPE = "POST_UPGRADE"
    VERSION = "0.0.1"

    def start(self, device, *args, **kwargs):
        """
        """

        cmd = "show running-config | in router isis"
        success, output = device.execute_command(cmd)
        if not success:
            self.error("show run | in router isis command failed {}\n{}".format(cmd, output))

	output = output.split('\n')
	output1 = device.session.send('configure', wait_for_string="(config)#")

	for line in output:
	    if re.search("router isis", line):
		val = "no " + line + " set-overload-bit"
		output1 = device.session.send(val, wait_for_string="(config)#")

	output1 = device.session.send('commit', wait_for_string="(config)#")
	output1 = device.session.send('end')
