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

from condoor.exceptions import CommandTimeoutError, CommandSyntaxError
from condoor import TIMEOUT
from horizon.plugin import PluginError, Plugin
from horizon.plugin_lib import wait_for_final_band
from horizon.plugins.cmd_capture import CmdCapturePlugin
from horizon.plugins.pre_migrate import XR_CONFIG_ON_DEVICE, ADMIN_CAL_CONFIG_ON_DEVICE, \
                                        ADMIN_XR_CONFIG_ON_DEVICE, XR_CONFIG_IN_CSM

TIMEOUT_FOR_COPY_CONFIG = 3600

_INVALID_INPUT = "Invalid input detected"

class PostMigratePlugin(Plugin):

    """
    A plugin for loading configurations and upgrade FPD's
    after the system migrated to ASR9K IOS-XR 64 bit(eXR).
    If any FPD needs upgrade, the device will be reloaded after
    the upgrade.
    Console access is needed.
    """
    NAME = "POST_MIGRATE"
    DESCRIPTION = "POST-MIGRATE FOR XR TO EXR MIGRATION"
    TYPE = "POST_MIGRATE"
    VERSION = "0.0.1"

    @staticmethod
    def _copy_file_from_eusb_to_harddisk(manager, device, filename, optional=False):
        """
        Copy file from eUSB partition(/eusbb/ in eXR) to /harddisk:.

        :param manager: the plugin manager
        :param device: the connection to the device
        :param filename: the string name of the file you want to copy from /eusbb
        :param optional: boolean value. If set to True, it's okay if the given filename
                         is not found in /eusbb/. If False, error out if the given filename
                         is missing from /eusbb/.
        :return: True if no error occurred.
        """

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
        """Quit the config mode without committing any changes."""
        def send_no(ctx):
            ctx.ctrl.sendline("no")
            return True

        def timeout(ctx):
            ctx.message = "Timeout upgrading FPD."
            return False

        UNCOMMITTED_CHANGES = re.compile("Uncommitted changes found, commit them\? \[yes/no/CANCEL\]")
        pat2 = "Uncommitted changes found, commit them before exiting\(yes/no/cancel\)\? \[cancel\]"
        UNCOMMITTED_CHANGES_2 = re.compile(pat2)
        RUN_PROMPT = re.compile("#")

        events = [UNCOMMITTED_CHANGES, UNCOMMITTED_CHANGES_2, RUN_PROMPT, TIMEOUT]
        transitions = [
            (UNCOMMITTED_CHANGES, [0], 1, send_no, 20),
            (UNCOMMITTED_CHANGES_2, [0], 1, send_no, 20),
            (RUN_PROMPT, [0], 0, None, 0),
            (RUN_PROMPT, [1], -1, None, 0),
            (TIMEOUT, [0, 1], -1, timeout, 0),

        ]

        if not device.run_fsm(PostMigratePlugin.DESCRIPTION, "end", events, transitions, timeout=60):
            manager.error("Failed to exit from the config mode. Please check session.log.")

    @staticmethod
    def _load_admin_config(manager, device, filename):
        """Load the admin/calvados configuration."""
        device.send("config", wait_for_string="#")

        output = device.send("load replace {}".format(filename), wait_for_string="#")

        if "Error" in output or "failed" in output:
            PostMigratePlugin.quit_config(manager, device)
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
        """Load the XR configuration."""
        device.send("config")

        output = device.send("load harddisk:/{}".format(filename))

        if "error" in output or "failed" in output:
            return PostMigratePlugin._handle_failed_commit(manager, output, device,
                                                           commit_with_best_effort, filename)

        output = device.send("commit")
        if "Failed" in output:
            return PostMigratePlugin._handle_failed_commit(manager, output, device,
                                                           commit_with_best_effort, filename)

        if "No configuration changes to commit" in output:
            manager.log("No configuration changes in /eusbb/{} were committed. ".format(filename) +
                        "Please check session.log.")
        if "Abort" in output:
            PostMigratePlugin.quit_config(manager, device)
            manager.error("Failure to commit configuration. Please check session.log for errors.")
        device.send("end")
        return True

    @staticmethod
    def _handle_failed_commit(manager, output, device, commit_with_best_effort, filename):
        """
        Display which line of config failed to load for which reason.
        If when scheduling Post-Migrate, user chooses to commit the migrated or
        self-selected custom XR config with best effort, we will commit the
        configs with best effort upon failure to load some configs, else, the loading
        will be aborted upon failure with some configs, the process errors out.

        :param manager: the plugin manager
        :param output: output after CLI "commit"
        :param device: the connection to the device
        :param commit_with_best_effort: 1 or -1. 1 for commiting with best effort.
                                        -1 for aborting commit upon error.
        :param filename: the string config filename in /eusbb/ that we are
                         trying to commit
        :return: True if no error occurred.
        """
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
                manager.log("No configuration changes in /eusbb/{} were committed. ".format(filename) +
                            "Please check session.log for errors.")
            device.send("end")

        return True

    @staticmethod
    def _check_fpds_for_upgrade(manager, device):
        """Check if any FPD's need upgrade, if so, upgrade all FPD's on all locations."""

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
        """
        Upgrade all FPD's on all locations.
        If after all upgrade completes, some show that a reload is required to reflect the changes,
        the device will be reloaded.

        :param manager: the plugin manager
        :param device: the connection to the device
        :param num_fpds: the number of FPD's that are in CURRENT and NEED UPGD states before upgrade.
        :return: True if upgraded successfully and reloaded(if necessary).
                 False if some FPD's did not upgrade successfully in 9600 seconds.
        """

        device.send("upgrade hw-module location all fpd all")

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
                    manager.log("Finished upgrading FPD(s). Now reloading the device to complete the upgrade.")
                    device.send("exit")
                    return PostMigratePlugin._reload_all(manager, device)
                return True

        # Some FPDs didn't finish upgrade
        return False

    @staticmethod
    def _reload_all(manager, device):
        """Reload the device with 1 hour maximum timeout"""
        device.reload(reload_timeout=3600, os=device.os_type)

        return PostMigratePlugin._wait_for_reload(manager, device)

    @staticmethod
    def _wait_for_reload(manager, device):
        """Wait for all nodes to come up with max timeout as 18 min"""
        # device.disconnect()
        # device.reconnect(max_timeout=300)
        manager.log("Waiting for all nodes to come to FINAL Band.")
        if wait_for_final_band(device):
            manager.log("All nodes are in FINAL Band.")
        else:
            manager.log("Warning: Not all nodes went to FINAL Band.")

        return True

    @staticmethod
    def start(manager, device, *args, **kwargs):

        try:
            best_effort_config = manager.csm.post_migrate_config_handling_option
        except AttributeError:
            manager.error("No configuration handling option selected when scheduling post-migrate.")

        manager.log("Waiting for all nodes to come to FINAL Band.")
        if not wait_for_final_band(device):
            manager.log("Warning: Not all nodes are in FINAL Band after 18 minutes.")

        manager.log("Loading the migrated Calvados configuration first.")
        device.send("admin")
        PostMigratePlugin._copy_file_from_eusb_to_harddisk(manager, device, ADMIN_CAL_CONFIG_ON_DEVICE)
        PostMigratePlugin._load_admin_config(manager, device, ADMIN_CAL_CONFIG_ON_DEVICE)

        try:
            # This is still in admin mode
            output = device.send("show running-config", timeout=2200)
            file_name = manager.file_name_from_cmd("admin show running-config")
            full_name = manager.save_to_file(file_name, output)
            if full_name:
                manager.save_data("admin show running-config", full_name)
            manager.log("Output of '{}' command saved to {}".format("admin show running-config", file_name))
        except Exception as e:
            manager.log(str(type(e)) + " when trying to capture 'admin show running-config'.")

        device.send("exit")

        manager.log("Loading the admin IOS-XR configuration on device.")
        file_exists = PostMigratePlugin._copy_file_from_eusb_to_harddisk(manager, device,
                                                                         ADMIN_XR_CONFIG_ON_DEVICE, optional=True)
        if file_exists:
            PostMigratePlugin._load_nonadmin_config(manager, device, ADMIN_XR_CONFIG_ON_DEVICE, best_effort_config)

        manager.log("Loading the IOS-XR configuration on device.")
        file_exists = PostMigratePlugin._copy_file_from_eusb_to_harddisk(manager, device, XR_CONFIG_ON_DEVICE)
        if file_exists:
            PostMigratePlugin._load_nonadmin_config(manager, device, XR_CONFIG_ON_DEVICE, best_effort_config)

        try:
            manager.csm.custom_commands = ["show running-config"]
            CmdCapturePlugin.start(manager, device)
        except Exception as e:
            manager.log(str(type(e)) + " when trying to capture 'show running-config'.")

        PostMigratePlugin._check_fpds_for_upgrade(manager, device)

        try:
            manager.csm.custom_commands = ["show platform"]
            CmdCapturePlugin.start(manager, device)
        except Exception as e:
            manager.log(str(type(e)) + " when trying to capture 'show platform'.")