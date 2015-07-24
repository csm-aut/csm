# =============================================================================
# migrate_xr_to_exr.py - plugin for migrating classic XR to eXR/fleXR
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

NOX_URL = 'http://wwwin-people.cisco.com/alextang/'
NOX_FILENAME_fetch = 'nox_linux_64bit_6.0.0v1.bin'
NOX_FILENAME = 'nox'

ROUTEPROCESSOR_RE = '(\d+/RS??P\d(?:/CPU\d*)?)'
LINECARD_RE = '[-\s](\d+/\d+(?:/CPU\d*)?)'
FPDS_CHECK_FOR_UPGRADE = set(['cbc', 'rommon', 'fpga2', 'fsbl', 'lnxfw'])
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
from au.condor.exceptions import CommandTimeoutError
from au.plugins.plugin import PluginError




# waiting long time (5 minutes)
TIME_OUT = 60



class MigrateToExrPlugin(IPlugin):

    """
    A plugin for migrating from XR to eXR/fleXR
    This plugin accesses rommon and set rommon variable EMT.
    A router is reloaded twice.
    Console access is needed.
    Arguments:
    T.B.D.
    """
    NAME = "MIGRATE_TO_EXR"
    DESCRIPTION = "XR TO EXR MIGRATION"
    TYPE = "MIGRATE"
    VERSION = "0.0.1"

    def _check_fpd(self, device):
        cmd = 'show hw-module fpd location all'
        success, fpdtable = device.execute_command(cmd)
        print cmd, '\n', fpdtable, "<-----------------", success

        if not success:
            self.error("Failed to check FPD version")
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

            pie_packages = []
            for package in packages:
                if package.find('.pie') > -1:
                    pie_packages.append(package)

            if len(pie_packages) < 2:
                self.error("ERROR: FPD upgrade needed but at least one of fpd pie and SMU package wasn't selected on your local repository.")

            """
            Step 1: Install add fpd pie and SMU
            Max Attempts = 2
            """
            install_add = InstallAddPlugin()
            try:
                install_add.start(device, repository=repo, pkg_file=pie_packages)
            except PluginError as e:
                self.log("Failed to install add in the first attempt - ({0}): {1}".format(e.errno, e.strerror))
                status = device.reconnect()
                if not status:
                    self.error("ERROR: failed to reconnect to the device after failing to install add in the first attempt. Please check log for how install add failed. Resolve any issue and start over the migration process.")
                install_add.start(device, repository=repo, pkg_file=pie_packages)

            print "fpd upgrade - successfully added smu"

            """
            Step 2: Install activate fpd pie and SMU
            Max Attempts = 2
            """

            install_act = InstallActivatePlugin()
            try:
                install_act.start(device, pkg_file=pie_packages)
            except PluginError as e:
                self.log("Failed to install activate in the first attempt - ({0}): {1}".format(e.errno, e.strerror))
                status = device.reconnect()
                if not status:
                    self.error("ERROR: failed to reconnect to the device after failing to install activate in the first attempt. Please check log for how install activate failed. Resolve any issue and start over the migration process.")
                install_act.start(device, repository=repo, pkg_file=pie_packages)

            print "fpd upgrade - successfully activated the smu"


            """
            Step 3: Install commit fpd pie and SMU
            Max Attempts = 2
            """

            install_com = InstallCommitPlugin()
            try:
                install_com.start(device)
            except PluginError as e:
                self.log("Failed to install commit in the first attempt - ({0}): {1}".format(e.errno, e.strerror))
                status = device.reconnect()
                if not status:
                    self.error("ERROR: failed to reconnect to the device after failing to install commit in the first attempt. Please check log for how install commit failed. Resolve any issue and start over the migration process.")
                install_com.start(device, repository=repo, pkg_file=pie_packages)


            print "fpd upgrade - successfully committed smu addition and activation"

            """
            Step 4: Upgrade all fpds in RP and Line card that need upgrade
            Max Attempts = 2 for each fpd upgrade
            """
            self._upgrade_all_fpds(device, location_to_subtypes_need_upgrade)

            print "fpd upgrade - successfully upgraded fpd"

            success_reload = self._reload_all(device)
            if success_reload:
                print "fpd upgrade - successfully reloaded"
                location_to_subtypes_need_upgrade = self._check_fpd(device)
                if location_to_subtypes_need_upgrade:
                    self.log("Command 'show hw-module fpd location all' shows some fpds in RP or Line card still need "
                             "upgrade even though they have just been upgraded. Either table content is incorrect or "
                             "fpd upgrade was unsuccessful. If it's latter, problem may arise later. \n fpds that shows not-upgraded: location : subtype(s) \n")
                    for location in location_to_subtypes_need_upgrade:
                        self.log(location + " : " + str(location_to_subtypes_need_upgrade[location]))


        return True

    def _upgrade_all_fpds(self, device, location_to_subtypes_need_upgrade):

        for location in location_to_subtypes_need_upgrade:

            for fpdtype in location_to_subtypes_need_upgrade[location]:

                print "fpd upgrade - starting to upgrade fpd subtype " + fpdtype + " in location " + location + "... "
                command = 'admin upgrade hw-module fpd ' + fpdtype + ' location ' + location + ' \r'
                success, output = device.execute_command(command, timeout=9600)
                print command, '\n', output, "<-----------------", success
                fpd_upgrade_success = re.search(location + '.*' + fpdtype + '[-_%.A-Z0-9a-z\s]*[Ss]uccess', output)
                if not fpd_upgrade_success:
                    if not re.search('[Nn]o.*' + fpdtype + '.*' + location + '.*need upgrade', output):
                        self._second_attempt_execution(device, command, 9600, [location + '.*' + fpdtype + '[-.A-Z0-9a-z\s]*[Ss]uccess', '[Nn]o.*' + fpdtype + '.*' + location + '.*need upgrade'], "failed to upgrade fpd subtype " + fpdtype + " in location " + location)
        return True

    def _second_attempt_execution(self, device, cmd, timeout, keywords, error_message):
        success, output = device.execute_command(cmd, timeout=timeout)
        print cmd, '\n', output, "<-----------------", success
        flag = False
        for keyword in keywords:
            if re.search(keyword, output):
                flag = True
                if not flag:
                    self.log(output.strip())
                    #print error_message + "\n Failed : " + cmd + " \n " + output
                    self.error("failed command '" + cmd.rstrip())

    def _save_config_to_repo(self, device, repository, filename):
        """
        Back up the configuration of the device in user's selected repository
        Max attempts: 2
        """
        cmd = 'copy running-config ' + repository + '/' + filename + ' \r \r'
        timeout = 120
        success, output = device.execute_command(cmd, timeout=timeout)
        print cmd, '\n', output, "<-----------------", success
        if not re.search('OK', output):
            self._second_attempt_execution(device, cmd, timeout, ['OK'], "failed to copy running-config to your repository.")



    def _save_config_to_csm_data(self, device, filename, fileloc):
        try:
            cmd="show run"
            timeout = 1000
            success, output = device.execute_command(cmd, timeout=timeout)
            print cmd, '\n', output, "<-----------------", success
            ind = output.rfind('Building configuration...\n')

        except CommandTimeoutError as e:
            success, output = device.execute_command(cmd, timeout=timeout*2)
            print cmd, '\n', output, "<-----------------", success


        if not os.path.exists(fileloc):
            self.error("ERROR: directory migration in csm_data not created during AUT execution")

        file = open(fileloc + '/' + filename, 'w+')
        #file = open('../../csm_data/migration/' + filename, 'w+')
        file.write(output[(ind+1):])
        file.close()



    def _copy_file_to_device(self, device, repository, filename, dest):
        timeout = 1500
        cmd = 'copy ' + repository + '/' + filename +' ' + dest +' \r \r'
        success, output = device.execute_command(cmd, timeout=timeout)
        print cmd, '\n', output, "<-----------------", success
        if not re.search('copied\s+in', output):
            self._second_attempt_execution(device, cmd, timeout, ['copied\s+in'], "failed to copy file to your repository.")


    def _apply_config(self, device, filename):
        cmd = 'admin config'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success


        cmd = 'load disk0:/' + filename + ' \r'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success


        # TO DO: confirm if commit replace or commit best-effort
        cmd = 'commit'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success

        cmd = 'end'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success

    def _resize_eusb(self, device, repository):
        print "trying to resize eusb..."
        self._copy_file_to_device(device, repository, 'resize_eusb', 'disk0:/')
        device.execute_command('run')
        cmd = 'ksh -x /disk0:/resize_eusb'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success
        device.execute_command('exit')


    def _set_emt_mode(self, device, repository):
        print "trying to set emt mode..."
        self._copy_file_to_device(device, repository, 'set_emt_mode', 'disk0:/')
        device.execute_command('run')
        cmd = 'ksh -x /disk0:/set_emt_mode'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success
        device.execute_command('exit')

    def _set_URL_NAME(self, device, repository):
        print "trying to set URL_NAME that points to flexr iso image..."
        device.execute_command('run')
        cmd = 'nvram_rommonvar URL_NAME ' + 'http://172.25.146.28/issus' + '/asr9k-mini-x64.iso'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success
        device.execute_command('exit')

    def _reload_all(self, device):
        cmd = 'admin reload location all \r \r'
        try:
            success, output = device.execute_command(cmd)
            print cmd, '\n', output, "<-----------------", success
            if success:
                return self._wait_for_reload(device)
        except CommandTimeoutError:
            print "Reload command - expected to timeout"
            return self._wait_for_reload(device)



    def _reload_rsp(self, device):
        cmd = 'admin reload location 0/RSP0/CPU0 \r \r'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success
        if success:
            return self._wait_for_reload(device)


    def _get_nox_binary_publish_date(self):
        try:
            url = NOX_URL + 'nox.lastPublishDate'
            r = requests.get(url)
            return r.text
        except:
            return None

    def _get_file_http(self, filename, destination):
        with open(destination + '/' + filename, 'wb') as handle:
            response = requests.get(NOX_URL + filename, stream=True)


            if not response.ok:
                self.error("ERROR: HTTP request to" + NOX_URL + filename + " failed.")

            print "request ok"
            for block in response.iter_content(1024):
                handle.write(block)

    def _is_conversion_successful(self, nox_output):
        match = re.search('Filename[\sA-Za-z\n]*[-\s]*\S*\s+(\d*)\s+\d*\(\s*\d%\)\s+\d*\(\s*\d%\)\s+(\d*)', nox_output)

        if match:
            print "matched " + match.group(1) + " to " + match.group(2)
            if match.group(1) == match.group(2):
                return True

        print "no match or matches not equal"
        return False



    def _wait_for_reload(self, device):
        """
         Wait for system to come up with max timeout as 25 Minutes

        """
        print "device trying to reconnect..."
        status = device.reconnect()
        print "device finished reconnecting..."
        # Connection to device failed
        if not status :
            return status

        print "device connection successful"

        # Connection to device is established , now look for all nodes to xr run state
        timeout = 1500
        poll_time = 30
        time_waited = 0
        xr_run = "IOS XR RUN"

        success = False
        cmd = "admin show platform"
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
                inventory = pkgutils.parse_xr_show_platform(output)
                if pkgutils.validate_xr_node_state(inventory, device):
                    return True

        # Some nodes did not come to run state
        return False



    def start(self, device, *args, **kwargs):

        repo_str = kwargs.get('repository', None)
        if not repo_str:
            self.error("ERROR:repository not provided")

        repo_str = 'tftp://1.75.1.1/joydai'

        fileloc = kwargs.get('fileloc', None)
        if not fileloc:
            fileloc = '../../csm_data/migration'
            noxloc = '../aut/au/plugins/'
            packages = kwargs.get("pkg_file", None)
            if not packages:
                self.error("ERROR:packages not provided")
        else:
            noxloc = './'
            packages = ['asr9k-fpd-px.pie-5.3.2.10I.SIT_IMAGE', 'asr9k-px-5.3.2.10I.CSCuu11794.pie']

        print "device name = " + device.name
        filename = device.name.replace(".", "_")
        filename = filename.replace(":", "_")

        """
        # checked: upgrade fpd if fpd needs upgrade
        self._ensure_updated_fpd(device, repo_str, packages)

        # repository = 'ftp://terastream:cisco@172.20.168.195/echami/'
        # checked: save the running configuration out of the box


        self._save_config_to_repo(device, repo_str, filename)

        self._save_config_to_csm_data(device, filename, fileloc)



        # checked: migrate config file to new config - need Eddie's tool

        date = self._get_nox_binary_publish_date()

        need_new_nox = False
        print "date = " + date
        if os.path.isfile(fileloc + '/' + 'nox.lastPublishDate'):
            with open(fileloc + '/' + 'nox.lastPublishDate', 'r') as f:
                current_date = f.readline()

            if date != current_date:
                need_new_nox = True

        else:
            need_new_nox = True

        if need_new_nox:
            self._get_file_http(NOX_FILENAME_fetch, fileloc)
            with open(fileloc + '/' + 'nox.lastPublishDate', 'w') as nox_publish_date_file:
                nox_publish_date_file.write(date)


        print "chmod" + "+x" + fileloc + '/' + NOX_FILENAME
        print fileloc + '/' + NOX_FILENAME + "-f" + fileloc + '/' + filename

        commands = [subprocess.Popen(["chmod", "+x", fileloc + '/' + NOX_FILENAME]), subprocess.Popen([fileloc + '/' + NOX_FILENAME, "-f", fileloc + '/' + filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)]




        # checked: copy iso, efi and cfg files to the FAT partition

        self._copy_file_to_device(device, repo_str, 'ipxe.efi', 'harddiskb:/efi/boot/grub.efi')


        # set URL_NAME rommon variable as path to eXR image, set emt mode to boot eXR from eUSB
        self._set_URL_NAME(device, repo_str)
        self._set_emt_mode(device, repo_str)


        # checked: reload router, now we have flexr-capable fpd
        #self._reload_all(device)



        # checked: after the reboot, store new config file back to router


        nox_output, nox_error = commands[1].communicate()

        print nox_output
        print nox_error
        conversion_success = self._is_conversion_successful(nox_output)

        if conversion_success:

            print "conversion is successful"

        else:
            self.error("configuration conversion is not successful.")

            #self._copy_file_to_device(device, repo_str, filename, 'disk0:/')


            # Yet to test: apply the config
            #self._apply_config(device, filename)

        """
        #return True


def main():
    device = Device(["telnet://root:root@172.25.146.221:2005"])
    #device = Device(["telnet://cisco:cisco@172.28.98.3"])
    #repo = 'ftp://terastream:cisco@172.20.168.195/echami'
    repo = 'tftp://1.75.1.1/joydai'

    device.connect()
    migration = MigrateToExrPlugin()
    migration.start(device, repository=repo, fileloc = '../../../../csm_data/migration')


if __name__ == "__main__":
    main()
