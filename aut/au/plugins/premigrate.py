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


import os
import subprocess
import re
import requests
import shutil
from database import DBSession
from models import Server
from smu_info_loader import IOSXR_URL, SMUInfoLoader


from constants import get_migration_directory
from utils import create_directory_in_migration


from au.plugins.plugin import IPlugin

NOX_64_BINARY = "nox_linux_64bit_6.0.0v3.bin"
NOX_32_BINARY = "nox_linux_32bit_6.0.0v3.bin"
NOX_PUBLISH_DATE = "nox_linux.lastPublishDate"
NOX_FOR_MAC = "nox"
MINIMUM_RELEASE_VERSION_FOR_MIGRATION = "5.3.2"
ACTIVE_PACKAGES_IN_CLASSIC = "active_packages_in_xr_snapshot.txt"




class PreMigratePlugin(IPlugin):

    """
    A plugin for migrating from XR to eXR/fleXR
    This plugin accesses rommon and set rommon variable EMT.
    A router is reloaded twice.
    Console access is needed.
    Arguments:
    T.B.D.
    """
    NAME = "PRE_MIGRATE"
    DESCRIPTION = "PRE-MIGRATE FOR XR TO EXR MIGRATION"
    TYPE = "PRE_MIGRATE"
    VERSION = "0.0.1"





    def _is_conversion_successful(self, nox_output):
        match = re.search('Filename[\sA-Za-z\n]*[-\s]*\S*\s+(\d*)\s+\d*\(\s*\d%\)\s+\d*\(\s*\d%\)\s+(\d*)', nox_output)

        if match:
            if match.group(1) == match.group(2):
                return True

        return False

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
            self.error("failed to copy running-config to your repository. Please check session.log for error and fix the issue.")

    def _upload_files_to_tftp(self, device, filenames, sourcefilepaths, repo_url):
        db_session = DBSession()
        server = db_session.query(Server).filter(Server.server_url == repo_url).first()
        if not server:
            self.error("Cannot map the tftp server url to the tftp server repository. Please check the tftp repository setup on CSM.")
        try:
            for x in range(0, len(sourcefilepaths)):
                shutil.copy(sourcefilepaths[x], server.server_directory + os.sep + filenames[x])
        except:
            db_session.close()
            self._disconnect_and_raise_error(device, "Exception was thrown while copying file from csm_data/migration/ to server repository directory")
        db_session.close()
        return True


    def _copy_files_to_device(self, device, repository, filenames, destpath):

        for filename in filenames:
            cmd = 'copy ' + repository + '/' + filename + ' ' + destpath + '/' + filename + ' \r \r'
            timeout = 120
            success, output = device.execute_command(cmd, timeout=timeout)
            print cmd, '\n', output, "<-----------------", success
            if re.search('[Ee]rror', output):
                self.error("Failed to copy configuration file from tftp server repository " + repository + '/' + filename + " to " + destpath + " on device.")

    def _disconnect_and_raise_error(self, device, msg):
        device.disconnect()
        self.log(msg)
        raise

    def _get_nox_binary_publish_date(self, device):
        try:
            url = IOSXR_URL + "/" + NOX_PUBLISH_DATE
            r = requests.get(url)
            if not r.ok:
                self.error("HTTP request to get " + IOSXR_URL + "/" + NOX_PUBLISH_DATE + " failed.")
            return r.text
        except:
            self._disconnect_and_raise_error(device, "Exception was thrown during HTTP request to get " + IOSXR_URL + "/" + NOX_PUBLISH_DATE + ". Disconnecting...")

    def _get_file_http(self, device, filename, destination):
        try:
            with open(destination + '/' + filename, 'wb') as handle:
                response = requests.get(IOSXR_URL + "/" + filename, stream=True)

                if not response.ok:
                    self.error("HTTP request to get " + IOSXR_URL + "/" + filename + " failed.")

                print "request ok"
                for block in response.iter_content(1024):
                    handle.write(block)
            handle.close()
        except:
            handle.close()
            self._disconnect_and_raise_error(device, "Exception was thrown during HTTP request to get " + IOSXR_URL + "/" + filename + " and writing it to csm_data/migration/. Disconnecting...")



    def _get_latest_config_migration_tool(self, device, fileloc):

        date = self._get_nox_binary_publish_date(device)

        need_new_nox = False

        if os.path.isfile(fileloc + '/' + NOX_PUBLISH_DATE):
            try:
                with open(fileloc + '/' + NOX_PUBLISH_DATE, 'r') as f:
                    current_date = f.readline()

                if date != current_date:
                    need_new_nox = True
                f.close()
            except:
                f.close()
                self._disconnect_and_raise_error(device, "Exception was thrown when reading file " + fileloc + "/" + NOX_PUBLISH_DATE + ". Disconnecting...")

        else:
            need_new_nox = True

        if need_new_nox:
            check_32_or_64_system = subprocess.Popen(['uname', '-a'], stdout=subprocess.PIPE)
            out, err = check_32_or_64_system.communicate()
            if err:
                self.error("Cannot determine whether the linux system that you are hosting CSM on is 32 bit or 64 bit. Please follow document to download the tools, convert the configurations and load them manually.")

            if "x86_64" in out:
                nox_to_use = NOX_64_BINARY
            else:
                nox_to_use = NOX_32_BINARY

            self._get_file_http(device, nox_to_use, fileloc)
            try:
                with open(fileloc + '/' + NOX_PUBLISH_DATE, 'w') as nox_publish_date_file:
                    nox_publish_date_file.write(date)
                nox_publish_date_file.close()
            except:
                nox_publish_date_file.close()
                self._disconnect_and_raise_error(device, "Exception was thrown when writing file " + fileloc + "/" + NOX_PUBLISH_DATE + ". Disconnecting...")


    def _take_out_breakout_config(self, filepath):
        breakout_config_empty = True
        if not os.path.isfile(filepath):
            self.error("The configuration file we backed up during Pre-Migrate - " + filepath + " - is not found.")
        classic_config = open(filepath, "r+")
        with open(filepath+"_breakout", 'w') as breakout_config:
            lines = classic_config.readlines()
            classic_config.seek(0)
            for line in lines:
                if "breakout" in line and "hw-module" in line:
                    breakout_config.write(line)
                    breakout_config_empty = False
                else:
                    classic_config.write(line)

            classic_config.truncate()
            classic_config.close()
            breakout_config.close()
        if breakout_config_empty:
            os.remove(filepath+"_breakout")
        return breakout_config_empty


    def _copy_files_to_csm_data(self, device, filenames, repo_url, dest_filenames):
        db_session = DBSession()
        server = db_session.query(Server).filter(Server.server_url == repo_url).first()
        if not server:
            self.error("Cannot map the tftp server url to the tftp server repository. Please check the tftp repository setup on CSM.")

        try:
            for x in range(0, len(filenames)):
                shutil.copy(server.server_directory + os.sep + filenames[x], dest_filenames[x])
        except:
            self._disconnect_and_raise_error(device, "Exception was thrown while copying file from server repository directory to device")

        db_session.close()

    def _post_status(self, msg):
        if self.csm_ctx:
            self.csm_ctx.post_status(msg)

    def _run_migration_on_config(self, fileloc, filename, nox_to_use):
        commands = [subprocess.Popen(["chmod", "+x", fileloc + os.sep + nox_to_use]), subprocess.Popen([fileloc + os.sep + nox_to_use, "-f", fileloc + os.sep + filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)]

        nox_output, nox_error = commands[1].communicate()

        if nox_error:
            self.error("Failed to run the configuration migration tool on the admin configuration we retrieved from device - " + nox_error)

        conversion_success = self._is_conversion_successful(nox_output)

        if conversion_success:

            self.csm_ctx.post_status("Finished migrating the admin configuration.")

        else:
            self.error("The migration of admin configuration is not successful. There may be lines not recognized by the configuration migration tool. If you still wish to migrate the system, you will need to manually load the correct configurations on eXR after system migration.")

    def _check_release_version(self, device):

        success, versioninfo = device.execute_command("show version")

        match = re.search('[Vv]ersion\s+?(\d\.\d\.\d)', versioninfo)

        if not match:
            self.error("Failed to recognize release version number. Please check session.log.")

        release_version = match.group(1)


        if release_version < MINIMUM_RELEASE_VERSION_FOR_MIGRATION:
            self.error("The minimal release version required for migration is 5.3.2. Please upgrade to at lease R5.3.2 before migration.")

    def _check_network_configuration(self, device, repo_str):

        device.execute_command("run")
        success, output = device.execute_command("nvram_rommonvar IP_ADDRESS")
        match = re.search('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', output)

        if not match:
            self.error("Please define rommon variable IP_ADDRESS. It's required for booting eXR.")

        success, output = device.execute_command("nvram_rommonvar DEFAULT_GATEWAY")
        match = re.search('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', output)

        if not match:
            self.error("Please define rommon variable DEFAULT_GATEWAY. It's required for booting eXR.")

        success, output = device.execute_command("nvram_rommonvar IP_SUBNET_MASK")
        match = re.search('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', output)

        if not match:
            self.error("Please define rommon variable IP_SUBNET_MASK. It's required for booting eXR.")

        device.execute_command("exit")

        repo_ip = re.search('.*/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/.*', repo_str)

        if not repo_ip:
            self.error("Bad hostname for server repository. Please check the settings in CSM.")

        success, output = device.execute_command("ping " + repo_ip.group(1))
        if "100 percent" not in output:
            self.error("Cannot ping server repository " + repo_ip.group(1) + " on device. Please check session.log.")


    def _snapshot_active_packages(self, device, fileloc):

        try:
            with open(fileloc + '/' + ACTIVE_PACKAGES_IN_CLASSIC, 'w') as active_packages_snapshot:

                success, output = device.execute_command('show install active summary')

                lines = output.split('\n')

                x = 0
                while "Active Packages:" not in lines[x]:
                    x += 1

                for i in range(x+1, len(lines)):
                    line = lines[i].strip()
                    active_packages_snapshot.write(line.split(":")[-1] + "\n")

            active_packages_snapshot.close()
        except:
            active_packages_snapshot.close()
            self._disconnect_and_raise_error(device, "Exception was thrown when writing file " + fileloc + "/" + ACTIVE_PACKAGES_IN_CLASSIC + ". Disconnecting...")




    def start(self, device, *args, **kwargs):

        repo_str = kwargs.get('repository', None)

        packages = kwargs.get("pkg_file", None)
        if not packages:
            packages = []

        host_directory = device.name.strip().replace('.', '_').replace(':','-')

        fileloc = get_migration_directory() + host_directory

        self.log(self.NAME + " Plugin is running")



        """
        self._post_status("Checking if migration requirements are met.")
        self._check_release_version(device)
        self._check_network_configuration(device, repo_str)


        self._post_status("Downloading latest configuration migration tool from CCO.")
        nox_to_use = self._get_latest_config_migration_tool(device, fileloc)



        self._post_status("Saving current configuration files on device into server repository and csm_data")
        self._copy_config_to_repo(device, repo_str, filename)


        success, output = device.execute_command('admin')
        if success:
            self._copy_config_to_repo(device, repo_str, filename + "_admin")
            device.execute_command('exit')


        self._copy_files_to_csm_data(device, [filename, filename + "_admin"], repo_str, [fileloc + os.sep + filename, fileloc + os.sep + filename + "_admin"])



        self._post_status("Converting admin configuration file with configuration migration tool")
        self._run_migration_on_config(fileloc, filename + "_admin", NOX_FOR_MAC)

        config_files = [filename, filename + "_admin.iox"]

        if not self._take_out_breakout_config(fileloc + os.sep + filename):
            config_files.append(filename + "_breakout")


        self._post_status("Uploading the migrated configuration files to server repository and device.")

        if self._upload_files_to_tftp(device, config_files, [fileloc + os.sep + config_name for config_name in config_files], repo_str):

            self._copy_files_to_device(device, repo_str, config_files, 'harddiskb:')




        self._snapshot_active_packages(device, fileloc)

        """


        return True

