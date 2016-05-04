#==============================================================
# node_status.py  - Plugin for checking Node states.
#
# Copyright (c)  2016, Cisco Systems
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


import re

from horizon.plugin import Plugin


class NodeStatusPlugin(Plugin):
    """
    NCS6K Pre-upgrade check
    This plugin checks states of all nodes
    """
    @staticmethod
    def _parse_show_platform(output, manager):
        inventory = {}
        lines = output.split('\n')

        for line in lines:
            line = line.strip()
            if len(line) > 0 and line[0].isdigit():
                states = re.split('\s\s+', line)
                if not re.search('CPU\d+$', states[0]):
                    continue
                node, node_type, state, admin_state, config_state = states
                entry = {
                    'type': node_type,
                    'state': state,
                    'admin_state':admin_state,
                    'config_state': config_state
                }
                inventory[node] = entry
        return inventory

    @staticmethod
    def start(manager, device, *args, **kwargs):
        """
        """
        output = device.send("admin show platform")
        inventory = NodeStatusPlugin._parse_show_platform(output,manager)

        valid_state = [
            'IOS XR RUN',
            'PRESENT',
            'READY',
            'FAILED',
            'OK',
            'DISABLED',
            'UNPOWERED',
            'ADMIN DOWN',
            'OPERATIONAL',
            'NOT ALLOW ONLIN',  # This is not spelling error
        ]
        for key, value in inventory.items():
            if 'CPU' in key:
                if value['state'] not in valid_state:
                    manager.log("{}={}: {}".format(key, value, "Not in valid state for upgrade"))
                    break
        else:
            manager.save_data("inventory", inventory)
            manager.log("All nodes in valid state for upgrade")
            return True
        manager.error("Not all nodes in correct state. Upgrade can not proceed")