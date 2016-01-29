# =============================================================================
# migrate_system.py - plugin for migrating classic XR to eXR/fleXR
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




import re
import time
from .plugin import PluginError, IPlugin
from ..package_lib import parse_exr_show_sdr, validate_exr_node_state
from ..plugin_lib import wait_for_reload

from condoor.exceptions import CommandTimeoutError




# waiting long time (5 minutes)
TIME_OUT = 60
SCRIPT_BACKUP_CONFIG = "harddiskb:/classic.cfg"
SCRIPT_BACKUP_ADMIN_CONFIG = "harddiskb:/admin.cfg"



class MigrateSystemToExrPlugin(IPlugin):

    """
    A plugin for migrating from XR to eXR/fleXR
    This plugin accesses rommon and set rommon variable EMT.
    A router is reloaded twice.
    Console access is needed.
    Arguments:
    T.B.D.
    """
    NAME = "MIGRATE_SYSTEM_TO_EXR"
    DESCRIPTION = "XR TO EXR SYSTEM MIGRATION"
    TYPE = "MIGRATE_SYSTEM"
    VERSION = "0.0.1"


    """
    @staticmethod
    def _copy_file_to_device(manager, device, repository, filename, dest):
        timeout = 1500
        success, output = device.execute_command('dir ' + dest + '/' + filename)
        cmd = 'copy ' + repository + '/' + filename + ' ' + dest
        device.execute_command(cmd, timeout=timeout, wait_for_string='?')

        if "No such file" not in output:
            device.execute_command('\r', timeout=timeout, wait_for_string='?')

        success, output = device.execute_command('\r', timeout=timeout)

        if re.search('copied\s+in', output):
            self._second_attempt_execution(device, cmd, timeout, 'copied\s+in', "failed to copy file to your repository.")
    """

    @staticmethod
    def _run_migration_script(manager, device):

        output = device.send("show platform")
        nodes = re.findall("(\d+/RS?P\d/CPU\d)", output)

        device.send("run", wait_for_string="#")

        if len(nodes) > 1:
            manager.log("Detected dual RP/RSP system.")

            output = device.send("show_platform", wait_for_string="#")
            node_name = re.search("My card name is -node(\d+_(RS?P)(\d)_CPU\d)-", output)
            if not node_name:
                manager.error("Failed to retrieve the node name from 'show_platform'. Please check session.log.")

            active_node = node_name.group(1).replace("_", "/")

            for node in nodes:

                if node != active_node:
                    output = device.send("iox_on {} ksh /pkg/bin/migrate_to_eXR -b eUSB -e 6".format(node), wait_for_string="#")

                    #MigrateSystemToExrPlugin._check_migration_script_output(manager, device, output)

        output = device.send("ksh /pkg/bin/migrate_to_eXR -b eUSB -e 5", wait_for_string="#")

        MigrateSystemToExrPlugin._check_migration_script_output(manager, device, output)

        device.send("exit")

        """
        device.send("run", wait_for_string="#")

        output = device.send("show_platform", wait_for_string="#")
        match = re.search("Act RP = (\d+) Stby (f{8}|\d+)", output)

        standby_node_num = match.group(2)

        if standby_node_num != "ffffffff":

            manager.log("Detected dual RP/RSP system.")
            node_name = re.search("My card name is -node(\d+_(RS?P)(\d)_CPU\d)-", output)

            if not node_name:
                manager.error("Failed to retrieve the node name from 'show_platform'. Please check session.log.")

            standby_node_name = node_name.group(1).replace("_", "/").replace(node_name.group(2) + node_name.group(3), node_name.group(2) + standby_node_num)


            output = device.send("iox_on {} ksh /pkg/bin/migrate_to_eXR -b eUSB -e 6".format(standby_node_name))

            #MigrateSystemToExrPlugin._check_migration_script_output(manager, device, output)


        output = device.send("ksh /pkg/bin/migrate_to_eXR -b eUSB -e 5", wait_for_string="#")


        MigrateSystemToExrPlugin._check_migration_script_output(manager, device, output)

        device.send("exit")
        """
        return True

    @staticmethod
    def _check_migration_script_output(manager, device, output):
        """
        check that the migration script ran without errors, and also, the configs are backed up.
        """
        lines = output.splitlines()
        for line in lines:
            if "No such file" in line:
                manager.error("Migration script is not found in /pkg/bin. Please upgrade your image to get access to the migration scripts under /pkg/bin/")
            if "Error:" in line:
                manager.error("Error when running migration script. Please check session.log.")
            if "Failed to correctly write emt_mode" in line:
                manager.error("Failed to write boot mode. Please check session.log")

        output = device.send('dir {}'.format(SCRIPT_BACKUP_CONFIG))
        if "No such file" in output:
            manager.error("Migration script failed to back up the running config. Please check session.log.")
        else:
            manager.log("The running-config is backed up in {}".format(SCRIPT_BACKUP_CONFIG))

        output = device.send('dir {}'.format(SCRIPT_BACKUP_ADMIN_CONFIG))
        if "No such file" in output:
            manager.error("Migration script failed to back up the admin running config. Please check session.log.")
        else:
            manager.log("The admin running-config is backed up in {}".format(SCRIPT_BACKUP_CONFIG))


    @staticmethod
    def _reload_all(manager, device):

        device.reload(reload_timeout=2000)

        #return MigrateSystemToExrPlugin._wait_for_reload(manager, device)
        return wait_for_reload(manager, device)



    @staticmethod
    def _wait_for_reload(manager, device):
        """
         Wait for system to come up with max timeout as 25 Minutes

        """
        device.disconnect()
        time.sleep(60)

        device.reconnect(max_timeout=1500)  # 25 * 60 = 1500
        timeout = 3600
        poll_time = 30
        time_waited = 0
        xr_run = "IOS XR RUN"

        cmd = "show sdr"
        manager.log("Waiting for all nodes to come up")
        time.sleep(100)
        while 1:
            # Wait till all nodes are in XR run state
            time_waited += poll_time
            if time_waited >= timeout:
                break
            time.sleep(poll_time)
            output = device.send(cmd)
            if xr_run in output:
                inventory = parse_exr_show_sdr(output)
                if validate_exr_node_state(inventory, device):
                    return True

        # Some nodes did not come to run state
        manager.error("Not all nodes have came up: {}".format(output))
        # this will never be executed
        return False



    @staticmethod
    def start(manager, device, *args, **kwargs):

        ctx = device.get_property("ctx")

        filename = ctx.host.hostname


        manager.log(MigrateSystemToExrPlugin.NAME + " Plugin is running")


        #self._post_status("Adding ipxe.efi to device")
        #self._copy_file_to_device(device, repo_str, 'ipxe.efi', 'harddiskb:/efi/boot/grub.efi')
        """

        manager.log("Run migration script to set boot mode and image path in device")
        success = MigrateSystemToExrPlugin._run_migration_script(manager, device)

        # checked: reload router, now we have flexr-capable fpd
        """
        if 1:
            manager.log("Reload device to boot eXR")
            MigrateSystemToExrPlugin._reload_all(manager, device)

        device.discovery()


        return True

