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
import re

from database import DBSession
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
    REGEX_CHASSIS = re.compile(r'chassis', flags=re.IGNORECASE)

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

        HostInventory <-- many to one relationship ---> Host

        Not for tree structured inventory storage.
        """
        pass

    def store_inventory(self, ctx, inventory_data, chassis_indices):
        """
        Store/update the processed inventory data in database
        :param ctx: context object
        :param inventory_data: parsed inventory data as a list of dictionaries
        :param chassis_indices: a list of index/indices of chassis inventory dictionary in inventory_data
        :return: None
        """
        if len(chassis_indices) == 0 or len(chassis_indices) > len(inventory_data):
            logger = get_db_session_logger(ctx.db_session)
            logger.exception('index/indices of chassis found in inventory output is out of range for host ' +
                             '{}.'.format(ctx.host.hostname))
            return

        # Assign the ordering or "position" of inventory in output from show inventory
        # to each inventory entry, but adjust the ordering so that chassis always have
        # negative position(s) (so as to mark corresponding inventory as chassis)
        # and non-chassis always have consecutive non-negative positions in ascending order,
        # It goes like this - if there is only one chassis, its position will be -1,
        # the non-chassis inventories will have positions starting from 0
        # If there are multiple chassis, for example 3 chassis, chassis 0 will have position -3,
        # chassis 1 will have position -2, chassis 2 will have position -1, non-chassis will
        # still have positions starting from 0
        chassis_position = 0 - len(chassis_indices)
        for chassis_idx in chassis_indices:
            inventory_data[chassis_idx]['position'] = chassis_position
            chassis_position += 1

        idx = 0
        position = 0
        rack_number = 0
        while idx < len(inventory_data):
            if rack_number < len(chassis_indices):
                if idx == chassis_indices[rack_number]:
                    rack_number += 1
                else:
                    inventory_data[idx]['position'] = position
                    position += 1
            else:
                inventory_data[idx]['position'] = position
                position += 1
            idx += 1

        db_session = DBSession()
        # this is necessary for now because somewhere in the thread, can be
        # anywhere in the code, the db_session was not closed - to be found out later.
        db_session.close()

        if len(ctx.host.host_inventory) > 0:
            self.compare_and_update(ctx, db_session, inventory_data)
        else:
            self.store_new_inventory(db_session, inventory_data, ctx.host.id)

        db_session.close()
        return

    def compare_and_update(self, ctx, db_session, inventory_data):
        """
        Update the processed inventory data in database
        :param ctx: context object
        :param db_session: database connection session
        :param inventory_data: parsed inventory data as a list of dictionaries
        :return: None
        """
        existing_host_inventory_query = db_session.query(HostInventory).filter(HostInventory.host_id == ctx.host.id)

        updated_inventory_ids = set()
        duplicate_serial_numbers = set()

        # Update existing host inventory based on the newly retrieved inventory data
        for retrieved_inventory_data in inventory_data:

            # existing_inventory_match is the existing HostInventory row(s) that
            # match(es) the serial number of the retrieved_inventory_data
            existing_inventory_match = None

            # Any existing HostInventory that has a serial_number == retrieved_inventory_data.get('serial_number')
            # would have already been deleted by the processing in a previous iteration
            if retrieved_inventory_data.get('serial_number') not in duplicate_serial_numbers:
                existing_inventory_match = \
                    existing_host_inventory_query.filter(HostInventory.serial_number ==
                                                         retrieved_inventory_data.get('serial_number')).all()

            self.set_extra_params_for_inventory(retrieved_inventory_data, ctx.host.id)

            #  existing_inventory_match is None or empty -
            #  no record in db matches the serial number of this retrieved_inventory_data,
            #  create new record for this one!
            if not existing_inventory_match:
                new_inventory = HostInventory(db_session, **retrieved_inventory_data)
                db_session.add(new_inventory)
                db_session.commit()
                updated_inventory_ids.add(new_inventory.id)
            else:
                # Single match in serial number found - update it!
                if len(existing_inventory_match) == 1:
                    existing_inventory_match[0].update(db_session, **retrieved_inventory_data)
                    updated_inventory_ids.add(existing_inventory_match[0].id)
                # Duplicate serial number matches found in db - delete all duplicates and create new
                # record for this retrieved_inventory_data.
                else:
                    duplicate_serial_numbers.add(retrieved_inventory_data.get('serial_number'))

                    [inv.delete(db_session) for inv in existing_inventory_match]
                    db_session.commit()

                    new_inventory = HostInventory(db_session, **retrieved_inventory_data)
                    db_session.add(new_inventory)
                    db_session.commit()
                    updated_inventory_ids.add(new_inventory.id)

        # Lastly, delete all inventories that are no longer found for this host in this retrieval
        for inventory in existing_host_inventory_query.all():
            if inventory.id not in updated_inventory_ids:
                inventory.delete(db_session)

        db_session.commit()

    def store_new_inventory(self, db_session, inventory_data, host_id):
        """
        Store all new inventory in the retrieved inventory data into database
        :param db_session: database connection session
        :param inventory_data: parsed inventory data as a list of dictionaries
        :param host_id: id of the host in database to which the inventory info belongs to
        :return: None
        """
        new_inventories = []
        for retrieved_inventory_data in inventory_data:
            # if this inventory data belongs to a chassis
            if retrieved_inventory_data.get('position') < 0:
                self.set_extra_params_for_inventory(retrieved_inventory_data, host_id, is_chassis=True)
            else:
                self.set_extra_params_for_inventory(retrieved_inventory_data, host_id)
            new_inventories.append(HostInventory(db_session, **retrieved_inventory_data))
        db_session.add_all(new_inventories)
        db_session.commit()

    def set_extra_params_for_inventory(self, inventory_dict, host_id, is_chassis=False):
        """
        Set the additional parameters for initializing a HostInventory row in database.
        :param inventory_dict: the inventory dictionary that's going to be used for
                               initializing a HostInventory object.
        :param host_id: id of the host in database to which the inventory info belongs to.
        :param is_chassis: True is the inventory is a chassis. False if it's not a chassis.
        :return: None
        """
        inventory_dict['host_id'] = host_id
        if is_chassis:
            rack_match = self.REGEX_RACK.search(inventory_dict['name'])
            if rack_match:
                inventory_dict['location'] = rack_match.group(0)
        else:
            location_match = self.REGEX_LOCATION.search(inventory_dict['name'])
            if location_match:
                inventory_dict['location'] = location_match.group(0)
            else:
                rack_match = self.REGEX_RACK.search(inventory_dict['name'])
                if rack_match:
                    inventory_dict['location'] = rack_match.group(0)
