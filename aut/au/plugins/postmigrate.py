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
import pexpect

import os

import requests
import shutil
from database import DBSession
from models import Server

#NOX_URL = 'http://wwwin-people.cisco.com/alextang/'
#NOX_FILENAME_fetch = 'nox_linux_64bit_6.0.0v1.bin'
#NOX_FILENAME = 'nox'

#"""

import sys

aut_path = os.path.join(os.path.dirname(__file__), '../../../aut')


# print aut_path
sys.path.append(aut_path)

from au.plugins.plugin import IPlugin
from au.device import Device
from au.lib import pkg_utils as pkgutils
from au.plugins.install_add import InstallAddPlugin
from au.plugins.install_commit import InstallCommitPlugin
from au.plugins.install_act import InstallActivatePlugin
from au.condor.exceptions import CommandTimeoutError,CommandSyntaxError
from au.plugins.plugin import PluginError

from constants import get_migration_directory
from au.condor.platforms.generic import _INVALID_INPUT





class PostMigratePlugin(IPlugin):

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

    def _copy_file_from_eusb_to_harddisk(self, device, filename, optional=False):
        cmd = 'run'
        device.execute_command(cmd, wait_for_string=']$')

        cmd = 'ls /eusbb/' + filename
        success, output = device.execute_command(cmd, wait_for_string=']$')

        if "No such file" in output:
            if not optional:
                self.error(filename + " is missing in /eusbb/ on device after migration.")
            else:
                device.execute_command('exit')
                return False

        cmd = 'cp /eusbb/' + filename + ' /harddisk:/' + filename
        success, output = device.execute_command(cmd, wait_for_string=']$')

        cmd = 'exit'
        device.execute_command(cmd)

        return True

    def _load_admin_config(self, device, filename):
        cmd = 'config'
        device.execute_command(cmd)

        cmd = 'load replace ' + filename
        success, output = device.execute_command(cmd)

        if "failed" in output or "Error" in output:
            device.execute_command('end', timeout=60, wait_for_string='?')
            device.execute_command('no', timeout=60)
            device.execute_command('exit')
            self.error("Aborted committing admin Calvados configuration. Please check session.log for errors.")
        else:
            success, output = device.execute_command('commit')
            if "failure" in output:
                device.execute_command('end', timeout=60, wait_for_string='?')
                device.execute_command('no', timeout=60)
                device.execute_command('exit')
                self.error("Failure to commit admin configuration. Please check session.log.")
            device.execute_command('end')


    def _load_nonadmin_config(self, device, filename, commit_with_best_effort):
        cmd = 'config'
        device.execute_command(cmd)

        cmd = 'load harddisk:/' + filename
        success, output = device.execute_command(cmd)

        if "error" in output or "failed" in output:
            return self._handle_failed_commit(output, device, commit_with_best_effort, filename)

        cmd = 'commit'
        success, output = device.execute_command(cmd)
        if "Failed" in output:
            return self._handle_failed_commit(output, device, commit_with_best_effort, filename)

        if "No configuration changes to commit" in output:
            self.log("No configuration changes in /eusbb/" + filename + " were committed. Please check session.log.")
        if "Abort" in output:
            device.execute_command('end', timeout=60, wait_for_string='?')
            device.execute_command('no', timeout=60)
            self.error("Failure to commit configuration. Please check session.log for errors.")
        device.execute_command('end')
        return True

    def _handle_failed_commit(self, output, device, commit_with_best_effort, filename):
        cmd = ''
        if "show configuration failed load [detail]" in output:
            cmd = 'show configuration failed load detail'
        elif "show configuration failed [inheritance]" in output:
            cmd = 'show configuration failed inheritance'
        if cmd:
            try:
                device.execute_command(cmd)
            except CommandSyntaxError as e:
                if not _INVALID_INPUT in e:
                    self.error("Should not come to this point.")

        print "commit_with_best_effort = " + str(commit_with_best_effort)
        if commit_with_best_effort == -1:
            device.execute_command('end', timeout=60, wait_for_string='?')
            device.execute_command('no', timeout=60)

            self.error("Errors when loading configuration. Please check session.log.")

        elif commit_with_best_effort == 1:
            cmd = 'commit best-effort force'
            success, output = device.execute_command(cmd)
            self.log("Committed configurations with best-effort. Please check session.log for result.")
            if "No configuration changes to commit" in output:
                self.log("No configuration changes in /eusbb/" + filename + " were committed. Please check session.log for errors.")
            device.execute_command('end')
            return True



    def _wait_for_final_band(self, device):
         # Wait for all nodes to Final Band
        timeout = 600
        poll_time = 20
        time_waited = 0
        xr_run = "IOS XR RUN"

        success = False
        cmd = "show platform vm"
        while 1:
            # Wait till all nodes are in XR run state
            time_waited += poll_time
            if time_waited >= timeout:
                break
            time.sleep(poll_time)
            success, output = device.execute_command(cmd)
            if success:
                if self._check_sw_status(output):
                    return True

        # Some nodes did not come to FINAL Band
        return False

    def _check_sw_status(self, output):
        lines = output.split('\n')

        for line in lines:
            line = line.strip()
            if len(line) > 0 and line[0].isdigit():
                sw_status = line[48:63].strip()
                if sw_status != "FINAL Band":
                    return False
        return True

    def _post_status(self, msg):
        if self.csm_ctx:
            self.csm_ctx.post_status(msg)


    def _check_fpds_for_upgrade(self, device):

        device.execute_command('admin')

        cmd = 'show hw-module fpd'
        success, fpdtable = device.execute_command(cmd)

        if not success:
            self.error("Failed to check FPD version before migration")

        match = re.search('\d+/\w+.+\d+.\d+\s+[-\w]+\s+(NEED UPGD)', fpdtable)

        if match:
            print "found items need upgrade"
            total_num = len(re.findall('NEED UPGD', fpdtable)) + len(re.findall('CURRENT', fpdtable))
            if not self._upgrade_all_fpds(device, total_num):
                self.error("FPD upgrade in eXR is not finished. Please check session.log.")
                return False


        device.execute_command('exit')
        return True


    def _upgrade_all_fpds(self, device, num_fpds):

        device.execute_command('upgrade hw-module location all fpd all')
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
            success, output = device.execute_command('show hw-module fpd')
            if success:
                num_need_reload = len(re.findall('RLOAD REQ', output))
                if len(re.findall('CURRENT', output)) + num_need_reload >= num_fpds:
                    if num_need_reload > 0:
                        print "need reload"
                        self._post_status("Finished upgrading FPD(s). Now reloading the device to complete the upgrade.")
                        return self._reload_all_in_admin(device)
                    return True

        # Some FPDs didn't finish upgrade
        return False


    def _reload_all_in_admin(self, device):
        #cmd = 'admin'
        #device.execute_command(cmd)
        cmd = 'hw-module location all reload'
        device.execute_command(cmd, wait_for_string='?')

        try:
            success, output = device.execute_command('yes')
            print cmd, '\n', output, "<-----------------", success
            if success:
                device.execute_command('\r')
        except CommandTimeoutError:
            print "Reload command - expected to timeout"

        return self._wait_for_reload(device)




    def _wait_for_reload(self, device):
        """
         Wait for system to come up with max timeout as 30 Minutes

        """
        print "device trying to reconnect..."
        status = device.reconnect()
        print "device finished reconnecting..."
        # Connection to device failed
        if not status :
            return status

        # Connection to device is established , now look for all nodes to xr run state
        timeout = 1500
        poll_time = 30
        time_waited = 0
        xr_run = "IOS XR RUN"

        success = False
        cmd = "show sdr"
        print "Waiting for all nodes to come up"
        time.sleep(60)
        while 1:
            # Wait till all nodes are in XR run state
            time_waited += poll_time
            if time_waited >= timeout:
                break
            time.sleep(poll_time)
            success, output = device.execute_command(cmd)
            if success and xr_run in output:
                inventory = pkgutils.parse_exr_show_sdr(output)
                if pkgutils.validate_exr_node_state(inventory, device):
                    return True

        # Some nodes did not come to run state
        return False





    def start(self, device, *args, **kwargs):


        #repo_str = kwargs.get('repository', None)
        #if not repo_str:
            #self.error("ERROR:repository not provided")


        fileloc = get_migration_directory()

        best_effort_config = kwargs.get('best_effort_config', None)

        print "device name = " + device.name
        filename = device.name.replace(".", "_")
        filename = filename.replace(":", "_")


        self.log(self.NAME + " Plugin is running")
        """

        self.log('best_effort_config = ' + str(best_effort_config))



        self._post_status("Waiting for all nodes to come to FINAL Band.")
        if not self._wait_for_final_band(device):
            self.error("Some nodes did not come to FINAL Band. Please load the configuration files at your discretion.")



        self._post_status("Loading the migrated Calvados configuration first.")
        cmd = 'admin'
        success, output = device.execute_command(cmd)
        if success:
            self._copy_file_from_eusb_to_harddisk(device, "admin.cal")
            self._load_admin_config(device, "admin.cal")
            cmd = 'exit'
            device.execute_command(cmd)
        else:
            self.error("Cannot enter admin mode on device. Please check session.log.")



        self._post_status("Loading the admin IOS-XR configuration on device.")
        file_exists = self._copy_file_from_eusb_to_harddisk(device, "admin.iox", optional=True)
        if file_exists:
            self._load_nonadmin_config(device, "admin.iox", best_effort_config)

        # if os.path.isfile(fileloc + os.sep + filename + "_breakout"):
        #     self._post_status("Loading the breakout configuration on device.")
        #     self._copy_file_from_eusb_to_harddisk(device, "breakout.cfg")
        #     self._load_nonadmin_config(device, "breakout.cfg", best_effort_config)


        self._post_status("Loading the IOS-XR configuration on device.")
        file_exists = self._copy_file_from_eusb_to_harddisk(device, "xr.iox")
        if file_exists:
            self._load_nonadmin_config(device, "xr.iox", best_effort_config)
        """
        self._check_fpds_for_upgrade(device)

        #self._reload_all(device)