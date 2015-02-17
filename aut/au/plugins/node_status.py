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


class NodeStatusPlugin(IPlugin):

    """
    ASR9k Pre-upgrade check
    This plugin checks states of all nodes
    """
    NAME = "NODE_STATUS"
    DESCRIPTION = "Node Status Check"
    TYPE = "PRE_UPGRADE_AND_POST_UPGRADE"
    VERSION = "0.0.1"

    def _parse_show_platform(self, device, output):
        inventory = {}
        lines = output.split('\n')
        platform = device.get_property('platform')
        for line in lines:
            line = line.strip()
            if len(line) > 0 and line[0].isdigit():
                states = re.split('\s\s+', line)
                if not re.search('CPU\d+$', states[0]):
                    continue
                if platform == 'crs':
                    node, type, plim, state, config_state = states
                else:
                    node, type, state, config_state = states
                entry = {
                    'type': type,
                    'state': state,
                    'config_state': config_state
                }
                inventory[node] = entry
        return inventory

    def start(self, device, *args, **kwargs):
        """
        """

        success, output = device.execute_command("admin show platform")
        if not success:
            return False

        inventory = self._parse_show_platform(device, output)

        valid_state = [
            'IOS XR RUN',
            'PRESENT',
            'READY',
            'FAILED',
            'OK',
            'DISABLED',
            'UNPOWERED',
            'ADMIN DOWN',
            'NOT ALLOW ONLIN',
        ]
        for key, value in inventory.items():
            if 'CPU' in key:
                if value['state'] not in valid_state:
                    print key, value['state'], 'Not in valid state for upgrade'
                    break
        else:
            device.store_property('inventory', inventory)
            self.log(
                "Device {} inventory captured".format(device.name)
            )
            return

        self.error("Not all nodes in correct state. Upgrade can not proceed.")
