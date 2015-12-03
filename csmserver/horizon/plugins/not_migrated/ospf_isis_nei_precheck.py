#==============================================================
# node_status.py  - Plugin for checking Node states.
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


class OspfIsisPrePlugin(IPlugin):

    """
    XR Pre-upgrade check
    This plugin checks states of all nodes
    """
    NAME = "OSPF_ISIS_NEIGHBOUR_PRE"
    DESCRIPTION = "OSPF ISIS neighbour precheck "
    TYPE = "PRE_UPGRADE"
    VERSION = "0.0.1"

    def start(self, device, *args, **kwargs):
        """
        """
        neighour_re = "Total neighbor count: (\d+)"

        cmd = "show ospf neighbor"
        success, output = device.execute_command(cmd)
        if not success:
            self.error("ospf neighbor check failed {}\n{}".format(cmd, output))
        if re.search(neighour_re, output):
            ospf_neighbor = re.search(neighour_re, output).group(1)
        else:
            ospf_neighbor = 0
        device.store_property('ospf_neighbor', ospf_neighbor)

        cmd = "show isis neighbor"
        success, output = device.execute_command(cmd)
        if not success:
            self.error("isis neighbor check failed {}\n{}".format(cmd, output))

        if re.search(neighour_re, output):
            isis_neighbor = re.search(neighour_re, output).group(1)
        else:
            isis_neighbor = 0
        device.store_property('isis_neighbor', isis_neighbor)
