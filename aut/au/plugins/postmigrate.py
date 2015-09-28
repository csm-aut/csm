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

    def _copy_file_from_eusb_to_harddisk(self, device, filename):
        cmd = 'run'
        success, output = device.execute_command(cmd)

        cmd = 'cp /eusbb/' + filename + ' /harddisk:/' + filename
        success, output = device.execute_command(cmd)

        if "No such file" in output:
            self.error(filename + " is missing in /eusbb/ on device after migration.")

        cmd = 'exit'
        success, output = device.execute_command(cmd)



    def _apply_config(self, device, repository, filename, commit_with_best_effort):

        self._copy_file_from_eusb_to_harddisk(device, filename)

        cmd = 'config'
        success, output = device.execute_command(cmd)

        cmd = 'load ' + repository + '/' + filename
        success, output = device.execute_command(cmd)

        if "failed" in output:

            if "show configuration failed load [detail]" in output:
                cmd = 'show configuration failed load detail'
                try:
                    success, output = device.execute_command(cmd)
                except CommandSyntaxError as e:
                    if not _INVALID_INPUT in e:
                        self.error("Should not come to this point.")

            if success and commit_with_best_effort == '-1':
                cmd = 'end \r no'
                device.execute_command(cmd)
                self.error("Errors when loading configuration. Please check session.log.")

            elif success and commit_with_best_effort == '1':
                cmd = 'commit'
                device.execute_command(cmd)
                self.log("Committed configurations with best-effort. Please check session.log for errors.")
                device.execute_command('end')
                return True

        cmd = 'commit'
        success, output = device.execute_command(cmd)

        cmd = 'end'
        success, output = device.execute_command(cmd)

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






    def start(self, device, *args, **kwargs):


        repo_str = kwargs.get('repository', None)
        if not repo_str:
            self.error("ERROR:repository not provided")


        fileloc = get_migration_directory()

        best_effort_config = kwargs.get('best_effort_config', None)

        print "device name = " + device.name
        filename = device.name.replace(".", "_")
        filename = filename.replace(":", "_")


        self.log(self.NAME + " Plugin is running")




        self._post_status("Waiting for all nodes to come to FINAL Band.")
        if not self._wait_for_final_band(device):
            self.error("Some nodes did not come to FINAL Band. Please load the configuration files at your discretion.")



        self._post_status("Applying the migrated admin configuration first.")
        cmd = 'admin'
        success, output = device.execute_command(cmd)
        if success:
            self._apply_config(device, repo_str, filename + "_admin", best_effort_config)
            cmd = 'exit'
            device.execute_command(cmd)
        else:
            self.error("Cannot enter admin mode on device. Please check session.log.")

        if os.path.isfile(fileloc + os.sep + filename + "_breakout"):
            self._post_status("Applying the breakout configuration to device.")
            self._apply_config(device, repo_str, filename + "_breakout", best_effort_config)


        self._post_status("Applying the configuration to device.")
        self._apply_config(device, repo_str, filename, best_effort_config)
