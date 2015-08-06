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



ROUTEPROCESSOR_RE = '(\d+/RS??P\d(?:/CPU\d*)?)'
LINECARD_RE = '[-\s](\d+/\d+(?:/CPU\d*)?)'
FPDS_CHECK_FOR_UPGRADE = set(['cbc', 'rommon', 'fpga2', 'fsbl', 'lnxfw'])
MINIMUM_RELEASE_VERSION_FOR_FLEXR_CAPABLE_FPD = '6.0.0'
#"""

import sys

aut_path = os.path.join(os.path.dirname(__file__), '..' + os.sep + '..' + os.sep + '..' + os.sep + 'aut')

# print aut_path
sys.path.append(aut_path)

from au.plugins.plugin import IPlugin
from au.device import Device
from au.lib import pkg_utils as pkgutils
from au.plugins.install_add import InstallAddPlugin
from au.plugins.install_commit import InstallCommitPlugin
from au.plugins.install_act import InstallActivatePlugin
from au.condor.exceptions import CommandTimeoutError
from au.plugins.plugin import PluginError



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
    TYPE = "MIGRATE"
    VERSION = "0.0.1"

    def _check_fpd(self, device):
        cmd = 'show hw-module fpd location all'
        success, fpdtable = device.execute_command(cmd)
        print cmd, '\n', fpdtable, "<-----------------", success

        if not success:
            self.error("Failed to check FPD version before migration")
            return -1

        location_to_subtypes_need_upgrade = {}

        self._find_all_fpds_need_upgrade(fpdtable, ROUTEPROCESSOR_RE, location_to_subtypes_need_upgrade)
        self._find_all_fpds_need_upgrade(fpdtable, LINECARD_RE, location_to_subtypes_need_upgrade)

        return location_to_subtypes_need_upgrade



    def _find_all_fpds_need_upgrade(self, fpdtable, location, location_to_subtypes_need_upgrade):
        for fpdtype in FPDS_CHECK_FOR_UPGRADE:
            match = re.search(location + '[-.A-Z0-9a-z\s]*?' + fpdtype + '[-.A-Z0-9a-z\s]*?(No|Yes)', fpdtable)

            if match:
                if match.group(2) == "Yes":
                    if not match.group(1) in location_to_subtypes_need_upgrade:
                        location_to_subtypes_need_upgrade[match.group(1)] = []
                    location_to_subtypes_need_upgrade[match.group(1)].append(fpdtype)


    def _ensure_updated_fpd(self, device, repo, packages):

        # check for the FPD version, if FPD needs upgrade,
        # enable the FPD Auto Upgrade Feature

        location_to_subtypes_need_upgrade = self._check_fpd(device)

        print "location_to_subtypes_need_upgrade = " + str(location_to_subtypes_need_upgrade)


        if location_to_subtypes_need_upgrade:

            cmd = "show install active summary"
            success, active_packages = device.execute_command(cmd)
            print cmd, '\n', active_packages, "<-----------------", success

            match = re.search('fpd', active_packages)

            if not match:
                self.error("Device needs FPD upgrade but no FPD pie is active on device. Please install FPD pie to try again or upgrade your FPDs to eXR capable FPDs.")


            cmd = "show version"
            success, versioninfo = device.execute_command(cmd)
            print cmd, '\n', versioninfo, "<-----------------", success

            match = re.search('[Vv]ersion\s+?(\d\.\d\.\d)', versioninfo)

            if not match:
                self.error("Failed to recognize release version number. Please check session.log.")

            release_version = match.group(1)


            if release_version < MINIMUM_RELEASE_VERSION_FOR_FLEXR_CAPABLE_FPD:


                pie_packages = []
                for package in packages:
                    if package.find('.pie') > -1:
                        pie_packages.append(package)

                if len(pie_packages) != 1:
                    self.error("Release version is below 6.0.0, please select exactly one FPD SMU pie on server repository for FPD upgrade. The filename must contain '.pie'")


                """
                Step 1: Install add the FPD SMU
                """
                self._post_status("FPD upgrade - install add the FPD SMU...")
                install_add = InstallAddPlugin()
                self._run_install_action_plugin(install_add, device, repo, pie_packages, "install add")


                """
                Step 2: Install activate the FPD SMU
                """
                self._post_status("FPD upgrade - install activate the FPD SMU...")
                install_act = InstallActivatePlugin()
                self._run_install_action_plugin(install_act, device, repo, pie_packages, "install activate")



                """
                Step 3: Install commit the FPD SMU
                """
                self._post_status("FPD upgrade - install commit the FPD SMU...")
                install_com = InstallCommitPlugin()
                self._run_install_action_plugin(install_com, device, repo, pie_packages, "install commit")



            """
            Force upgrade all fpds in RP and Line card that need upgrade, with the FPD pie or both the FPD pie and FPD SMU depending on release version
            """
            self._upgrade_all_fpds(device, location_to_subtypes_need_upgrade)


        return True

    def _run_install_action_plugin(self, install_plugin, device, repo, pie_packages, install_action_name):
        try:
            install_plugin.start(device, repository=repo, pkg_file=pie_packages)
        except PluginError as e:
            self.error("Failed to " + install_action_name + " the FPD SMU - ({0}): {1}".format(e.errno, e.strerror))
        except AttributeError:
            device.disconnect()
            self.log("Disconnected...")
            raise PluginError("Failed to " + install_action_name + " the FPD SMU. Please check session.log for details of failure.")



    def _upgrade_all_fpds(self, device, location_to_subtypes_need_upgrade):

        for location in location_to_subtypes_need_upgrade:

            for fpdtype in location_to_subtypes_need_upgrade[location]:

                self._post_status("FPD upgrade - start to upgrade FPD subtype " + fpdtype + " in location " + location)

                command = 'admin upgrade hw-module fpd ' + fpdtype + ' force location ' + location + ' \r'
                success, output = device.execute_command(command, timeout=9600)
                print command, '\n', output, "<-----------------", success
                #fpd_upgrade_success = re.search(location + '.*' + fpdtype + '[-_%.A-Z0-9a-z\s]*[Ss]uccess', output)
                fpd_upgrade_success = re.search('[Ss]uccess', output)
                if not fpd_upgrade_success:
                    self.error("Failed to force upgrade FPD subtype " + fpdtype + " in location " + location)

        return True

    def _post_status(self, msg):
        if self.csm_ctx:
            self.csm_ctx.post_status(msg)

    def _second_attempt_execution(self, device, cmd, timeout, keyword, error_message):
        success, output = device.execute_command(cmd, timeout=timeout)
        print cmd, '\n', output, "<-----------------", success
        if not re.search(keyword, output):
            self.error(error_message)

    def _copy_config_to_repo(self, device, repository, filename):
        """
        Back up the configuration of the device in user's selected repository
        Max attempts: 2
        """
        cmd = 'copy running-config ' + repository + '/' + filename + ' \r \r'
        timeout = 120
        success, output = device.execute_command(cmd, timeout=timeout)
        print cmd, '\n', output, "<-----------------", success
        if not re.search('OK', output):
            self._second_attempt_execution(device, cmd, timeout, 'OK', "failed to copy running-config to your repository.")





    def _copy_file_to_device(self, device, repository, filename, dest):
        timeout = 1500
        cmd = 'copy ' + repository + '/' + filename +' ' + dest +' \r \r'
        success, output = device.execute_command(cmd, timeout=timeout)
        print cmd, '\n', output, "<-----------------", success
        if not re.search('copied\s+in', output):
            self._second_attempt_execution(device, cmd, timeout, 'copied\s+in', "failed to copy file to your repository.")



    def _migrate_to_eXR(self, device, repository):
        device.execute_command('run')
        iso_path = 'http://172.25.146.28/issus' + '/asr9k-mini-x64.iso'
        cmd = 'ksh /harddiskb:' + os.sep + 'migrate_to_eXR ' + iso_path
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success

        """
        check that URL_NAME and emt mode has been set correctly.

        """
        match = re.search(iso_path, output)
        if not match:
            self.error("Failed to assign the path to eXR image to rommon variable URL_NAME. Please check session.log")

        match = re.search('memory location (0x[A-Z0-9a-z]+)', output)

        if match:
            cmd = 'mem_rd ' + match.group(1) + ' 1'
            success, memory_read_output = device.execute_command(cmd)
            match = re.search('00000005\s12345678', memory_read_output)
            if not match:
                self.error("Failed to write boot mode in memory. 'mem_wr' may have failed. Please check session.log")


        success, output = device.execute_command('exit')
        return success


    def _reload_all(self, device):
        cmd = 'admin reload location all \r'
        try:
            success, output = device.execute_command(cmd)
            print cmd, '\n', output, "<-----------------", success
            if success:
                device.execute_command('\r')
                return self._wait_for_reload(device)
        except CommandTimeoutError:
            print "Reload command - expected to timeout"
            return self._wait_for_reload(device)

    def _copy_config_to_csm_data(self, filename, repo_url, dest_filename):
        db_session = DBSession()
        server = db_session.query(Server).filter(Server.server_url == repo_url).first()
        if not server:
            self.error("Cannot map the tftp server url to the tftp server repository. Please check the tftp repository setup on CSM.")
        shutil.copy(server.server_directory + os.sep + filename, dest_filename)
        db_session.close()


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

        repo_str = kwargs.get('repository', None)
        if not repo_str:
            self.error("Server Repository not provided")


        packages = kwargs.get("pkg_file", None)
        if not packages:
            packages = []


        fileloc = get_migration_directory()

        print "device name = " + device.name
        filename = device.name.replace(".", "_")
        filename = filename.replace(":", "_")


        self.log(self.NAME + " Plugin is running")

        """

        self._post_status("Checking FPD version...")
        self._ensure_updated_fpd(device, repo_str, packages)


        self._post_status("Backing up configuration")
        self._copy_config_to_repo(device, repo_str, filename)

        self._copy_config_to_csm_data(filename, repo_str, fileloc + os.sep + filename)



        self._post_status("Adding ipxe.efi to device")
        self._copy_file_to_device(device, repo_str, 'ipxe.efi', 'harddiskb:/efi/boot/grub.efi')


        self._post_status("Setting boot mode and image path in device")
        success = self._migrate_to_eXR(device, repo_str)

        # checked: reload router, now we have flexr-capable fpd
        if success:
            self._post_status("Reload device to boot eXR")
            self._reload_all(device)

        """

        return True

