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

from models import get_db_session_logger, HostInventory, Inventory


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

    REGEX_BASIC_PATTERN = re.compile(r'NAME:\s*"?(?P<name>.*?)"?,?\s*DESCR:\s*"?(?P<description>.*?)"?\W*PID:\s*(?P<model_name>.*?)\s*,?\s*VID:\s*(?P<hardware_revision>.*?)\s*,?\s*SN:\s*(?!NAME)(?P<serial_number>\S*)\s*',
                                     flags=re.MULTILINE | re.IGNORECASE)
    REGEX_LOCATION = re.compile(r'\d(?:/[*a-zA-Z0-9]+)+')
    REGEX_RACK = re.compile(r'rack \d+', flags=re.IGNORECASE)

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
        return [m.groupdict() for m in self.REGEX_BASIC_PATTERN.finditer(output)]

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
        """
        pass

    def store_inventory(self, ctx, inventory_data, chassis_idx):
        """
        Store/update the processed inventory data in database
        :param ctx: context object
        :param inventory_data: parsed inventory data as a list of dictionaries
        :param chassis_idx: the index of chassis inventory dictionary in inventory_data
        :return: None
        """
        if chassis_idx > len(inventory_data) or chassis_idx < 0:
            logger = get_db_session_logger(ctx.db_session)
            logger.exception('chassis index in inventory output is out of range for host {}.'.format(ctx.host.hostname))
            return

        # Assign the ordering or "position" of inventory in output from show inventory
        # to each inventory entry, but adjust the ordering so that chassis always comes first
        inventory_data[chassis_idx]['position'] = 0
        for idx in xrange(0, chassis_idx):
            inventory_data[idx]['position'] = idx + 1
        for idx in xrange(chassis_idx + 1, len(inventory_data)):
            inventory_data[idx]['position'] = idx

        db_session = DBSession()

        if len(ctx.host.host_inventory) > 0:
            self.compare_and_update(ctx, db_session, inventory_data, chassis_idx)
        else:
            self.store_new_inventory(db_session, inventory_data, ctx.host.id, chassis_idx)
        db_session.commit()

    def compare_and_update(self, ctx, db_session, inventory_data, chassis_idx):
        """
        Update the processed inventory data in database
        :param ctx: context object
        :param db_session: database connection session
        :param inventory_data: parsed inventory data as a list of dictionaries
        :param chassis_idx: the index of chassis inventory dictionary in inventory_data
        :return: None
        """
        existing_host_inventory_query = db_session.query(HostInventory).filter(HostInventory.host_id == ctx.host.id)
        updated_inventory_ids = set()

        # Firstly, update chassis inventory in db
        existing_chassis_inventory = existing_host_inventory_query.filter(HostInventory.parent_id == None).first()

        chassis_inventory = self.update_chassis_inventory(db_session, ctx.host.id,
                                                          existing_chassis_inventory,
                                                          inventory_data[chassis_idx])
        updated_inventory_ids.add(chassis_inventory.id)

        duplicate_serial_numbers = set()

        # Secondly, update existing host inventory based on the newly retrieved inventory data
        for retrieved_inventory_data in inventory_data:
            # only process non-chassis inventories here
            if retrieved_inventory_data.get('position') != 0:

                # existing_inventory_match is the existing HostInventory row(s) that
                # match(es) the serial number of the retrieved_inventory_data
                existing_inventory_match = None

                # Any existing HostInventory that has a serial_number == retrieved_inventory_data.get('serial_number')
                # would have already been deleted by the processing in a previous iteration
                if retrieved_inventory_data.get('serial_number') not in duplicate_serial_numbers:
                    existing_inventory_match = \
                        existing_host_inventory_query.filter(HostInventory.serial_number ==
                                                             retrieved_inventory_data.get('serial_number')).all()

                self.set_extra_params_for_nonchassis(retrieved_inventory_data, ctx.host.id, chassis_inventory)

                #  existing_inventory_match is None or empty -
                #  no record in db matches the serial number of this retrieved_inventory_data,
                #  create new record for this one!
                if not existing_inventory_match:
                    new_inventory = HostInventory(db_session, **retrieved_inventory_data)
                    db_session.flush()
                    updated_inventory_ids.add(new_inventory.id)
                else:
                    # Single match in serial number found - update it!
                    if len(existing_inventory_match) == 1:
                        existing_inventory_match[0].update(db_session, **retrieved_inventory_data)
                        updated_inventory_ids.add(existing_inventory_match[0].id)
                    # Duplicate serial number matches found in db - delete all duplicates and create new
                    # record for this retrieved_inventory_data!
                    else:
                        duplicate_serial_numbers.add(retrieved_inventory_data.get('serial_number'))

                        [inv.delete(db_session) for inv in existing_inventory_match if inv.id != chassis_inventory.id]
                        db_session.flush()

                        new_inventory = HostInventory(db_session, **retrieved_inventory_data)
                        db_session.flush()
                        updated_inventory_ids.add(new_inventory.id)

        # Lastly, delete all inventories that are no longer found for this host in this retrieval
        for inventory in existing_host_inventory_query.all():
            if inventory.id not in updated_inventory_ids:
                inventory.delete(db_session)
        db_session.flush()

    def store_new_inventory(self, db_session, inventory_data, host_id, chassis_idx):
        """
        Store all new inventory in the retrieved inventory data into database
        :param db_session: database connection session
        :param inventory_data: parsed inventory data as a list of dictionaries
        :param host_id: id of the host in database to which the inventory info belongs to
        :param chassis_idx: the index of chassis inventory dictionary in inventory_data
        :return: None
        """
        retrieved_chassis_data = inventory_data[chassis_idx]
        self.set_extra_params_for_chassis(retrieved_chassis_data, host_id)
        chassis_inventory = HostInventory(db_session, **retrieved_chassis_data)

        for retrieved_inventory_data in inventory_data:
            # only process non-chassis inventories here
            if retrieved_inventory_data.get('position') != 0:
                self.set_extra_params_for_nonchassis(retrieved_inventory_data, host_id, chassis_inventory)
                HostInventory(db_session, **retrieved_inventory_data)

        db_session.add(chassis_inventory)

    def set_extra_params_for_nonchassis(self, inventory_dict, host_id, chassis_inventory):
        """
        Set the additional parameters for initializing a non-chassis HostInventory row in database.
        :param inventory_dict: the inventory dictionary that's going to be used for
                               initializing a HostInventory object.
        :param host_id: id of the host in database to which the inventory info belongs to.
        :param chassis_inventory: the chassis inventory object that this inventory is under.
                     The chassis inventory is going to be made the parent of this inventory.
        :return: None
        """
        inventory_dict['parent'] = chassis_inventory
        inventory_dict['host_id'] = host_id
        location_match = self.REGEX_LOCATION.search(inventory_dict['name'])
        if location_match:
            inventory_dict['location'] = location_match.group(0)
        else:
            rack_match = self.REGEX_RACK.search(inventory_dict['name'])
            if rack_match:
                inventory_dict['location'] = rack_match.group(0)

    def set_extra_params_for_chassis(self, retrieved_chassis_data, host_id):
        """
        Set the additional parameters for initializing a chassis HostInventory row in database.
        :param retrieved_chassis_data: the dictionary with chassis inventory data that's going
                                        to be used for initializing the HostInventory object.
        :param host_id: id of the host in database to which the inventory info belongs to.
        :return: None
        """
        retrieved_chassis_data['host_id'] = host_id
        rack_match = self.REGEX_RACK.search(retrieved_chassis_data['name'])
        if rack_match:
            retrieved_chassis_data['location'] = rack_match.group(0)

    def update_chassis_inventory(self, db_session, host_id, existing_chassis_inventory, retrieved_chassis_data):
        """
        Update the chassis inventory data in db
        :param db_session: database session
        :param host_id: the id of the host that this chassis belongs to
        :param existing_chassis_inventory: existing chassis inventory object found in database - the potential
                                             object to update on
        :param retrieved_chassis_data: the dictionary that contains the newly retrieved chassis inventory data
        :return: either the updated existing_chassis_inventory or the newly created HostInventory object
                that contains the newly retrieved chassis inventory data
        """

        self.set_extra_params_for_chassis(retrieved_chassis_data, host_id)

        if existing_chassis_inventory:
            existing_chassis_inventory.update(db_session, **retrieved_chassis_data)
            return existing_chassis_inventory

        chassis_inventory = HostInventory(db_session, **retrieved_chassis_data)
        db_session.add(chassis_inventory)
        db_session.flush()

        return chassis_inventory
