# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
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
from abc import abstractmethod
from models import get_db_session_logger, HostInventory
import re

inventory_location_regex = '\d(?:/[*a-zA-Z0-9]+)+'
inventory_rack_regex = 'rack \d+'


class BaseInventoryProcessor(object):
    @abstractmethod
    def process(self, ctx, inventory_data):
        """
        Store inventory information in database in format:
        HostInventory for chassis <-- many to one relationship --> Host
            |
            | children:
            |
            |__ All other HostInventory in the chassis

        :return: None
        """
        pass

    def store(self, ctx, inventory_data, chassis_ind):
        if chassis_ind > len(inventory_data) or chassis_ind < 0:
            logger = get_db_session_logger(ctx.db_session)
            logger.exception('chassis index in inventory output is out of range for host {}.'.format(ctx.host.hostname))
            return
        print "inventory_dict = " + str(inventory_data[chassis_ind])
        ctx.host.inventory = HostInventory(**inventory_data[chassis_ind])
        for i in xrange(0, len(inventory_data)):
            if i != chassis_ind:
                inventory_dict = inventory_data[i]
                inventory_dict['parent'] = ctx.host.inventory
                inventory_dict['host_id'] = ctx.host.id
                location_match = re.search(inventory_location_regex, inventory_dict['name'])
                if location_match:
                    inventory_dict['location'] = location_match.group(0)
                else:
                    rack_match = re.search(inventory_rack_regex, inventory_dict['name'], flags=re.IGNORECASE)
                    if rack_match:
                        inventory_dict['location'] = rack_match.group(0)
                print "inventory_dict = " + str(inventory_dict)
                # HostInventory(**inventory_dict)
