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
import subprocess
import requests
import shutil
from database import DBSession
from models import Server
from constants import get_migration_directory



#"""

import sys

aut_path = os.path.join(os.path.dirname(__file__), '..' + os.sep + '..' + os.sep + '..' + os.sep + 'aut')

# print aut_path
sys.path.append(aut_path)

from au.plugins.plugin import IPlugin
from au.device import Device
from au.lib import pkg_utils as pkgutils

from au.condor.exceptions import CommandTimeoutError
from au.plugins.plugin import PluginError
from au.plugins.device_connect import DeviceConnectPlugin


from parsers.platforms.iosxr import BaseCLIPackageParser
from au.plugins.package_state import get_package


# waiting long time (5 minutes)
TIME_OUT = 60



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



    def _post_status(self, msg):
        if self.csm_ctx:
            self.csm_ctx.post_status(msg)

    def _second_attempt_execution(self, device, cmd, timeout, keyword, error_message):
        success, output = device.execute_command(cmd, timeout=timeout)
        print cmd, '\n', output, "<-----------------", success
        if not re.search(keyword, output):
            self.error(error_message)




    def _copy_file_to_device(self, device, repository, filename, dest):
        timeout = 1500
        success, output = device.execute_command('dir ' + dest + '/' + filename)
        cmd = 'copy ' + repository + '/' + filename + ' ' + dest +' \r'
        if "No such file" not in output:
            cmd += ' \r'

        success, output = device.execute_command(cmd, timeout=timeout)

        if re.search('copied\s+in', output):
            self._second_attempt_execution(device, cmd, timeout, 'copied\s+in', "failed to copy file to your repository.")



    def _migrate_to_eXR(self, device):


        device.execute_command('run')
        #iso_path = 'http://172.25.146.28/issus' + '/asr9k-mini-x64.iso'
        cmd = 'ksh /harddiskb:/migrate_to_eXR '
        success, output = device.execute_command(cmd)

        """
        check that URL_NAME and emt mode has been set correctly.

        """
        if "No such file" in output:
            self.error("No migration script is found on device. Please download the 'migrate_to_eXR' script to the server repository and select it prior to scheduling migration.")

        #if not iso_path in output:
        #    self.error("Failed to assign the path to eXR image to rommon variable URL_NAME. Please check session.log")

        success, output = device.execute_command('exit')
        return success


    def _reload_all(self, device):
        cmd = 'admin reload location all \r'
        try:
            success, output = device.execute_command(cmd)
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
        status = device.reconnect(connect_with_reconfiguration=True)
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
        time.sleep(100)
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


        packages = kwargs.get("pkg_file", None)
        if not packages:
            packages = []


        fileloc = get_migration_directory()

        print "device name = " + device.name
        filename = device.name.replace(".", "_")
        filename = filename.replace(":", "_")


        self.log(self.NAME + " Plugin is running")


        #self._post_status("Adding ipxe.efi to device")
        #self._copy_file_to_device(device, repo_str, 'ipxe.efi', 'harddiskb:/efi/boot/grub.efi')


        self._post_status("Setting boot mode and image path in device")
        success = self._migrate_to_eXR(device)

        # checked: reload router, now we have flexr-capable fpd
        if success:
            self._post_status("Reload device to boot eXR")
            self._reload_all(device)




        success, output = device.execute_command("show version")
        match = re.search('Version\s(.*)\s', output)
        if match:
            if self.csm_ctx and self.csm_ctx.host:
                self.csm_ctx.host.software_version = match.group(1)
                self.csm_ctx.host.software_platform = 'asr9k-x'



        get_package(device)

        parser = BaseCLIPackageParser()
        if self.csm_ctx and self.csm_ctx.host:
            parser.get_packages_from_cli(self.csm_ctx.host, install_inactive_cli=self.csm_ctx.inactive_cli, install_active_cli=self.csm_ctx.active_cli, install_committed_cli=self.csm_ctx.committed_cli)

        return True

