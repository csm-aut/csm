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
import abc
from database import DBSession
import re

from models import get_db_session_logger, HostInventory

inventory_pattern = r'NAME:\s*"?(?P<name>.*?)"?,?\s*DESCR:\s*"?(?P<description>.*?)"?\W*PID:\s*(?P<model_name>.*?)\s*,?\s*VID:\s*(?P<hardware_revision>.*?)\s*,?\s*SN:\s*(?!NAME)(?P<serial_number>\S*)\s*'
inventory_location_regex = '\d(?:/[*a-zA-Z0-9]+)+'
inventory_rack_regex = 'rack \d+'


class BaseSoftwarePackageParser(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def set_host_packages_from_cli(self, ctx, install_inactive_cli=None,
                                   install_active_cli=None, install_committed_cli=None):
        """
        parse the software package info from CLI output and set it to the host context.
        """
        return


class BaseInventoryParser(object):
    __metaclass__ = abc.ABCMeta

    def parse_inventory_output(self, output):
        """
        For all platforms.
        Parse the inventory output into a list of dictionaries, each dictionary is an inventory entry.
        Example result:
            [{'description': 'ASR 9006 4 Line Card Slot Chassis with V1 AC PEM',
              'hardware_revision': 'V01',
              'serial_number': 'FOX1523H7HA',
              'model_name': 'ASR-9006-AC',
              'name': 'chassis ASR-9006-AC'},
             {'description': 'ASR9K Route Switch Processor with 440G/slot Fabric and 12GB',
             'hardware_revision': 'V01',
             'serial_number': 'FOC160785RB',
             'model_name': 'A9K-RSP440-SE',
             'name': 'module 0/RSP0/CPU0'}
             ...]

        :param output: output from "admin show inventory" or "show inventory" depending on the platform.
        :return: A list of dictionaries each containing 5 keys/values.
                 keys: 'description', 'hardware_revision', 'serial_number', 'model_name' and 'name'.
        """
        flags = re.MULTILINE
        flags |= re.IGNORECASE
        return [m.groupdict() for m in re.finditer(inventory_pattern, output, flags=flags)]

    @abc.abstractmethod
    def process_inventory(self, ctx):
        """
        Store newly retrieved inventory information for a host in database for the below structure:

        HostInventory for chassis <-- many to one relationship ---> Host
            ^                                                         ^
            | one to many parent/children relationship                | many to one relationship
            |                                                         |
             --> All other HostInventory in the chassis <-------------

        Not for tree structured inventory storage.
        :return: None
        """
        return

    def store_inventory(self, ctx, inventory_data, chassis_ind):
        """
        Store/update the processed inventory data in database
        :param ctx: context object
        :param inventory_data: parsed inventory data as a list of dictionaries
        :param chassis_ind: the index of chassis inventory dictionary in inventory_data
        :return: None
        """
        if chassis_ind > len(inventory_data) or chassis_ind < 0:
            logger = get_db_session_logger(ctx.db_session)
            logger.exception('chassis index in inventory output is out of range for host {}.'.format(ctx.host.hostname))
            return

        inventory_data[chassis_ind]['position'] = 0
        for i in xrange(0, chassis_ind):
            inventory_data[i]['position'] = i + 1
        for i in xrange(chassis_ind + 1, len(inventory_data)):
            inventory_data[i]['position'] = i

        db_session = DBSession()
        # del ctx.host.inventory[:]
        # db_session.commit()
        if len(ctx.host.inventory) > 0:
            self.compare_and_update(ctx, db_session, inventory_data, chassis_ind)
        else:
            self.store_new_inventory(db_session, inventory_data, ctx.host.id, chassis_ind)
        db_session.commit()

    def compare_and_update(self, ctx, db_session, inventory_data, chassis_ind):
        """
        Update the processed inventory data in database
        :param ctx: context object
        :param db_session: database connection session
        :param inventory_data: parsed inventory data as a list of dictionaries
        :param chassis_ind: the index of chassis inventory dictionary in inventory_data
        :return: None
        """
        all_host_inventory = db_session.query(HostInventory).filter(HostInventory.host_id == ctx.host.id)
        updated_inventory_ids = set()

        new_chassis_inventory = inventory_data[chassis_ind]
        chassis_inventory = all_host_inventory.filter(HostInventory.parent_id == None).first()
        if not chassis_inventory:
            del ctx.host.inventory[:]
            db_session.flush()
            self.store_new_inventory(db_session, inventory_data, ctx.host.id, chassis_ind)
            db_session.commit()
            logger = get_db_session_logger(ctx.db_session)
            logger.exception(
                'No chassis inventory information found in database for host {}.'.format(ctx.host.hostname))
            return
        else:
            self.set_extra_params_for_chassis(new_chassis_inventory, ctx.host.id)
            chassis_inventory.update(**new_chassis_inventory)
            updated_inventory_ids.add(chassis_inventory.id)

        duplicate_serial_numbers = set()
        for i in xrange(0, len(inventory_data)):
            if i != chassis_ind:
                new_inventory = inventory_data[i]

                if new_inventory['serial_number'] in duplicate_serial_numbers:
                    existing_inventory = None
                else:
                    existing_inventory = all_host_inventory.filter(HostInventory.serial_number ==
                                                                   new_inventory['serial_number']).all()

                self.set_extra_params(new_inventory, ctx.host.id, chassis_inventory)

                #  None or empty
                if not existing_inventory:
                    create_newinv = HostInventory(**new_inventory)
                    db_session.flush()
                    updated_inventory_ids.add(create_newinv.id)
                elif len(existing_inventory) > 1:
                    duplicate_serial_numbers.add(new_inventory['serial_number'])

                    [db_session.delete(inv) for inv in existing_inventory if inv.id != chassis_inventory.id]
                    db_session.flush()

                    create_newinv = HostInventory(**new_inventory)
                    db_session.flush()
                    updated_inventory_ids.add(create_newinv.id)
                else:
                    existing_inventory[0].update(**new_inventory)
                    updated_inventory_ids.add(existing_inventory[0].id)

        for inventory in all_host_inventory.all():
            if inventory.id not in updated_inventory_ids:
                db_session.delete(inventory)
        db_session.flush()

    def store_new_inventory(self, db_session, inventory_data, host_id, chassis_ind):
        """
        Store new inventory info in database
        :param db_session: database connection session
        :param inventory_data: parsed inventory data as a list of dictionaries
        :param host_id: id of the host in database to which the inventory info belongs to
        :param chassis_ind: the index of chassis inventory dictionary in inventory_data
        :return: None
        """
        new_chassis_inventory = inventory_data[chassis_ind]
        self.set_extra_params_for_chassis(new_chassis_inventory, host_id)
        chassis_inventory = HostInventory(**new_chassis_inventory)

        for i in xrange(0, len(inventory_data)):
            if i != chassis_ind:
                self.set_extra_params(inventory_data[i], host_id, chassis_inventory)
                HostInventory(**inventory_data[i])

        db_session.add(chassis_inventory)

    def set_extra_params(self, inventory_dict, host_id, chassis_inventory):
        """
        Set the additional parameters for initiating a non-chassis HostInventory row in database.
        :param inventory_dict: the inventory dictionary that's going to be used for
                               initiating a HostInventory object.
        :param host_id: id of the host in database to which the inventory info belongs to.
        :param chassis_inventory: the chassis inventory object that this inventory is under.
                     The chassis inventory is going to be made the parent of this inventory.
        :return: None
        """
        inventory_dict['parent'] = chassis_inventory
        inventory_dict['host_id'] = host_id
        location_match = re.search(inventory_location_regex, inventory_dict['name'])
        if location_match:
            inventory_dict['location'] = location_match.group(0)
        else:
            rack_match = re.search(inventory_rack_regex, inventory_dict['name'], flags=re.IGNORECASE)
            if rack_match:
                inventory_dict['location'] = rack_match.group(0)

    def set_extra_params_for_chassis(self, chassis_inventory, host_id):
        """
         Set the additional parameters for initiating a chassis HostInventory row in database.
        :param chassis_inventory: the chassis inventory dictionary that's going to be used for
                               initiating the HostInventory object.
        :param host_id: id of the host in database to which the inventory info belongs to.
        :return: None
        """
        chassis_inventory['host_id'] = host_id
        rack_match = re.search(inventory_rack_regex, chassis_inventory['name'], flags=re.IGNORECASE)
        if rack_match:
            chassis_inventory['location'] = rack_match.group(0)

