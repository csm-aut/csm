# =============================================================================
# check_isis_neighbours - Plugin for checking number of ISIS neighbours
#
# Copyright (c)  2015, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
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
from ..plugin_lib import save_data, load_data
from time import time
from datetime import datetime


class ISISNeighborCountPlugin(IPlugin):

    """
    ASR9k Pre-upgrade check
    This plugin check the number of ISIS Neighbors and store this information in format
    {
        <instance>: {
            "Up": [ <L1>, <L2>, <L1/L2> ],
            "Init": [ <L1>, <L2>, <L1/L2> ],
            "Failed": [ <L1>, <L2>, <L1/L2> ]
        }
    }

    """
    NAME = "ISIS_NEIGHBORS"
    DESCRIPTION = "ISIS Neighbors Check"
    TYPE = "PRE_UPGRADE_AND_POST_UPGRADE"
    VERSION = "1.0.0"
    FAMILY = ["ASR9K"]

    @staticmethod
    def start(manager, device, *args, **kwargs):
        cmd = "show isis neighbor summary"
        isis_neighbor_info = {}
        output = device.send(cmd)
        if output:
            isis_instance = None
            for line in output.split('\n'):
                result = re.search('IS-IS (\w+) neighbor summary:', line)
                if result:
                    isis_instance = result.group(1)
                    isis_neighbor_info[isis_instance] = {}
                    continue
                result = re.search('Up\s+(\d+)\s+(\d+)\s+(\d+)', line)
                if result and isis_instance:
                    isis_neighbor_info[isis_instance]["Up"] = [result.group(n) for n in range(1, 4)]
                    continue
                result = re.search('Init\s+(\d+)\s+(\d+)\s+(\d+)', line)
                if result and isis_instance:
                    isis_neighbor_info[isis_instance]["Init"] = [result.group(n) for n in range(1, 4)]
                    continue
                result = re.search('Failed\s+(\d+)\s+(\d+)\s+(\d+)', line)
                if result and isis_instance:
                    isis_neighbor_info[isis_instance]["Failed"] = [result.group(n) for n in range(1, 4)]
                    continue

            if isis_instance:
                manager.info("There is {} ISIS protocol instance(s) active".format(len(isis_neighbor_info)))
                for instance, state_dict in isis_neighbor_info.items():
                    for state, neighbors in state_dict.items():
                        manager.info("Instance {} {:<6} L1={} L2={} L1L2={}".format(instance, state, *neighbors))
                if manager.phase == "PRE_UPGRADE":
                    save_data(device, "isis_neighbors", isis_neighbor_info)
            else:
                manager.info("No ISIS protocol instance active")

            if manager.phase == "POST_UPGRADE":
                    ISISNeighborCountPlugin.compare_data(manager, device, "isis_neighbors", isis_neighbor_info)


    @staticmethod
    def compare_data(manager, device, storage_key, current_data):
        levels = ["L1", "L2", "L1L2"]
        try:
            previous_data, timestamp = load_data(device, storage_key)
        except ValueError:
            manager.warning("No data stored from Pre-Upgrade phase. Can't compare.")
            return

        if previous_data:
            manager.info("Pre-Upgrade phase data available for comparison")
            manager.info("Pre-Upgrade data collected on {}".format(
                datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')))
            if timestamp < time() - (60 * 60 * 2):  # two hours
                manager.warning("Pre-Upgrade phase data older than 2 hours")

            for previous_instance, previous_state_dict in previous_data.items():
                try:
                    current_state_dict = current_data[previous_instance]
                except KeyError:
                    manager.warning("No ISIS instance '{}' detected after upgrade".format(previous_instance))
                    continue

                for state, previous_neighbors in previous_state_dict.items():
                    current_neighbors = current_state_dict[state]
                    if previous_neighbors != current_neighbors:
                        for level in range(3):
                            if previous_neighbors[level] != current_neighbors[level]:
                                manager.warning(
                                    "Number of ISIS neighbors for instance '{}' in state {} at {} is different"
                                    "Pre-Install={} Post-Install={}".format(
                                        previous_instance, state, levels[level], previous_neighbors[level],
                                        current_neighbors[level]
                                    )
                                )
                else:
                    manager.info("Number of ISIS neighbors for instance '{}' is the "
                                 "same as during pre-install check".format(previous_instance))
        else:
            manager.warning("No data stored from Pre-Upgrade phase")
            return

