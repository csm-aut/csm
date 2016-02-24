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

import os

#NOX_URL = 'http://wwwin-people.cisco.com/alextang/'
#NOX_FILENAME_fetch = 'nox_linux_64bit_6.0.0v1.bin'
#NOX_FILENAME = 'nox'

#"""


from horizon.plugin import PluginError, Plugin
from horizon.package_lib import parse_exr_show_sdr, validate_exr_node_state
from condoor.exceptions import CommandTimeoutError, CommandSyntaxError
from horizon.plugins.pre_migrate import XR_CONFIG_ON_DEVICE, ADMIN_CAL_CONFIG_ON_DEVICE, ADMIN_XR_CONFIG_ON_DEVICE
from condoor import TIMEOUT


_INVALID_INPUT = "Invalid input detected"

class PostMigratePlugin(Plugin):

    """
    A plugin for migrating from XR to eXR/fleXR
    Console access is needed.
    Arguments:
    T.B.D.
    """
    NAME = "POST_MIGRATE"
    DESCRIPTION = "POST-MIGRATE FOR XR TO EXR MIGRATION"
    TYPE = "POST_MIGRATE"
    VERSION = "0.0.1"

    @staticmethod
    def _copy_file_from_eusb_to_harddisk(manager, device, filename, optional=False):
        device.send("run", wait_for_string="\]\$")

        output = device.send("ls /eusbb/{}".format(filename), wait_for_string="\]\$")

        if "No such file" in output:
            if not optional:
                manager.error("{} is missing in /eusbb/ on device after migration.".format(filename))
            else:
                device.send("exit")
                return False

        device.send("cp /eusbb/{0} /harddisk:/{0}".format(filename), wait_for_string="\]\$")

        device.send("exit")

        return True

    @staticmethod
    def quit_config(manager, device):

        def send_no(ctx):
            ctx.ctrl.sendline("no")
            return True

        UNCOMMITTED_CHANGES = re.compile("Uncommitted changes found, commit them\? \[yes/no/CANCEL\]")
        UNCOMMITTED_CHANGES_2 = re.compile("Uncommitted changes found, commit them before exiting\(yes/no/cancel\)\? \[cancel\]")
        RUN_PROMPT = re.compile("#")

        events = [UNCOMMITTED_CHANGES, UNCOMMITTED_CHANGES_2, RUN_PROMPT, TIMEOUT]
        transitions = [
            (UNCOMMITTED_CHANGES, [0], 1, send_no, 20),
            (UNCOMMITTED_CHANGES_2, [0], 1, send_no, 20),
            (RUN_PROMPT, [0], 0, None, 0),
            (RUN_PROMPT, [1], -1, None, 0),
            (TIMEOUT, [0, 1], 2, None, 0),

        ]

        if not device.run_fsm(PostMigratePlugin.DESCRIPTION, "end", events, transitions, timeout=60):
            manager.error("Failed to exit from the config mode. Please check session.log.")


    @staticmethod
    def _load_admin_config(manager, device, filename):
        device.send("config", wait_for_string="#")

        output = device.send("load replace {}".format(filename), wait_for_string="#")

        if "Error" in output or "failed" in output:
            PostMigratePlugin.quit_config(manager, device)
            #device.send("end", timeout=60, wait_for_string='?')
            #device.send('no', timeout=60)
            device.send("exit")
            manager.error("Aborted committing admin Calvados configuration. Please check session.log for errors.")
        else:
            output = device.send("commit", wait_for_string="#")
            if "failure" in output:
                PostMigratePlugin.quit_config(manager, device)
                device.send("exit")
                manager.error("Failure to commit admin configuration. Please check session.log.")
            device.send("end")


    @staticmethod
    def _load_nonadmin_config(manager, device, filename, commit_with_best_effort):

        device.send("config")

        output = device.send("load harddisk:/{}".format(filename))

        if "error" in output or "failed" in output:
            return PostMigratePlugin._handle_failed_commit(manager, output, device, commit_with_best_effort, filename)

        output = device.send("commit")
        if "Failed" in output:
            return PostMigratePlugin._handle_failed_commit(manager, output, device, commit_with_best_effort, filename)

        if "No configuration changes to commit" in output:
            manager.log("No configuration changes in /eusbb/{} were committed. Please check session.log.".format(filename))
        if "Abort" in output:
            PostMigratePlugin.quit_config(manager, device)
            manager.error("Failure to commit configuration. Please check session.log for errors.")
        device.send("end")
        return True


    @staticmethod
    def _handle_failed_commit(manager, output, device, commit_with_best_effort, filename):

        cmd = ""
        if "show configuration failed load [detail]" in output:
            cmd = "show configuration failed load detail"
        elif "show configuration failed [inheritance]" in output:
            cmd = "show configuration failed inheritance"

        if cmd:
            try:
                device.send(cmd)
            except CommandSyntaxError as e:
                pass

        print "commit_with_best_effort = " + str(commit_with_best_effort)
        if commit_with_best_effort == -1:
            PostMigratePlugin.quit_config(manager, device)

            manager.error("Errors when loading configuration. Please check session.log.")

        elif commit_with_best_effort == 1:
            output = device.send("commit best-effort force")
            manager.log("Committed configurations with best-effort. Please check session.log for result.")
            if "No configuration changes to commit" in output:
                manager.log("No configuration changes in /eusbb/{} were committed. Please check session.log for errors.".format(filename))
            device.send("end")
            return True


    @staticmethod
    def _wait_for_final_band(device):
         # Wait for all nodes to Final Band
        timeout = 600
        poll_time = 20
        time_waited = 0
        xr_run = "IOS XR RUN"

        cmd = "show platform vm"
        while 1:
            # Wait till all nodes are in XR run state
            time_waited += poll_time
            if time_waited >= timeout:
                break
            time.sleep(poll_time)
            output = device.send(cmd)
            if PostMigratePlugin._check_sw_status(output):
                return True

        # Some nodes did not come to FINAL Band
        return False

    @staticmethod
    def _check_sw_status(output):
        lines = output.splitlines()

        for line in lines:
            line = line.strip()
            if len(line) > 0 and line[0].isdigit():
                sw_status = line[48:63].strip()
                if sw_status != "FINAL Band":
                    return False
        return True


    @staticmethod
    def _check_fpds_for_upgrade(manager, device):

        device.send("admin")

        fpdtable = device.send("show hw-module fpd")


        match = re.search("\d+/\w+.+\d+.\d+\s+[-\w]+\s+(NEED UPGD)", fpdtable)

        if match:
            total_num = len(re.findall("NEED UPGD", fpdtable)) + len(re.findall("CURRENT", fpdtable))
            if not PostMigratePlugin._upgrade_all_fpds(manager, device, total_num):
                manager.error("FPD upgrade in eXR is not finished. Please check session.log.")
                return False


        device.send("exit")
        return True


    @staticmethod
    def _upgrade_all_fpds(manager, device, num_fpds):

        device.send("upgrade hw-module location all fpd all")
        print "issued upgrade command"

        timeout = 9600
        poll_time = 30
        time_waited = 0

        time.sleep(60)
        while 1:
            # Wait till all FPDs finish upgrade
            time_waited += poll_time
            if time_waited >= timeout:
                break
            time.sleep(poll_time)
            output = device.send("show hw-module fpd")
            num_need_reload = len(re.findall("RLOAD REQ", output))
            if len(re.findall("CURRENT", output)) + num_need_reload >= num_fpds:
                if num_need_reload > 0:
                    print "need reload"
                    manager.log("Finished upgrading FPD(s). Now reloading the device to complete the upgrade.")
                    device.send("exit")
                    return PostMigratePlugin._reload_all(manager, device)
                return True

        # Some FPDs didn't finish upgrade
        return False

    @staticmethod
    def _reload_all(manager, device):

        device.reload(reload_timeout=3600, os=device.os_type)

        return PostMigratePlugin._wait_for_reload(manager, device)




    @staticmethod
    def _wait_for_reload(manager, device):
        """
         Wait for system to come up with max timeout as 30 min

        """
        device.disconnect()
        #time.sleep(10)

        device.reconnect(max_timeout=300)
        timeout = 1800
        poll_time = 30
        time_waited = 0
        xr_run = "IOS XR RUN"

        cmd = "show sdr"
        manager.log("Waiting for all nodes to come up")
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


        fileloc = manager.csm.migration_directory

        try:
            best_effort_config = manager.csm.post_migrate_config_handling_option
        except AttributeError:
            manager.error("No configuration handling option selected when scheduling post-migrate.")


        filename = manager.csm.host.hostname


        manager.log("Waiting for all nodes to come to FINAL Band.")
        if not PostMigratePlugin._wait_for_final_band(device):
            manager.error("Not all nodes are in FINAL Band. Please check session.log.")



        manager.log("Loading the migrated Calvados configuration first.")
        output = device.send("admin")
        PostMigratePlugin._copy_file_from_eusb_to_harddisk(manager, device, ADMIN_CAL_CONFIG_ON_DEVICE)
        PostMigratePlugin._load_admin_config(manager, device, ADMIN_CAL_CONFIG_ON_DEVICE)
        device.send("exit")



        manager.log("Loading the admin IOS-XR configuration on device.")
        file_exists = PostMigratePlugin._copy_file_from_eusb_to_harddisk(manager, device, ADMIN_XR_CONFIG_ON_DEVICE, optional=True)
        if file_exists:
            PostMigratePlugin._load_nonadmin_config(manager, device, ADMIN_XR_CONFIG_ON_DEVICE, best_effort_config)

        # if os.path.isfile(fileloc + os.sep + filename + "_breakout"):
        #     self._post_status("Loading the breakout configuration on device.")
        #     self._copy_file_from_eusb_to_harddisk(device, "breakout.cfg")
        #     self._load_nonadmin_config(device, "breakout.cfg", best_effort_config)


        manager.log("Loading the IOS-XR configuration on device.")
        file_exists = PostMigratePlugin._copy_file_from_eusb_to_harddisk(manager, device, XR_CONFIG_ON_DEVICE)
        if file_exists:
            PostMigratePlugin._load_nonadmin_config(manager, device, XR_CONFIG_ON_DEVICE, best_effort_config)

        PostMigratePlugin._check_fpds_for_upgrade(manager, device)

