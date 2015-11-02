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
import csv
from database import DBSession
from models import Server
from smu_info_loader import IOSXR_URL, SMUInfoLoader


from constants import get_migration_directory
from utils import create_directory_in_migration


from au.plugins.plugin import PluginError, IPlugin
from au.plugins.node_status import NodeStatusPlugin
from au.plugins.install_add import InstallAddPlugin
from au.plugins.install_commit import InstallCommitPlugin
from au.plugins.install_act import InstallActivatePlugin

from sets import Set

NOX_64_BINARY = "nox_linux_64bit_6.0.0v3.bin"
NOX_32_BINARY = "nox_linux_32bit_6.0.0v3.bin"
NOX_FOR_MAC = "nox-mac64"
MINIMUM_RELEASE_VERSION_FOR_MIGRATION = "5.3.3"
MAXIMUM_RELEASE_VERSION_FOR_MIGRATION = "6.0.0"
ACTIVE_PACKAGES_IN_CLASSIC = "active_packages_in_xr_snapshot.txt"

TIMEOUT_FOR_COPY_CONFIG = 1000

TIMEOUT_FOR_COPY_ISO = 1000
ISO_FULL_IMAGE_NAME = "asr9k-full-x64.iso"
ISO_MINI_IMAGE_NAME = "asr9k-mini-x64.iso"

GRUB_EFI_NAME = "grub.efi"
GRUB_CFG_NAME = "grub.cfg"

ROUTEPROCESSOR_RE = '(\d+/RS??P\d(?:/CPU\d*)?)'
LINECARD_RE = '[-\s](\d+/\d+(?:/CPU\d*)?)'
FPDS_CHECK_FOR_UPGRADE = set(['cbc', 'rommon', 'fpga2', 'fsbl', 'lnxfw'])
MINIMUM_RELEASE_VERSION_FOR_FLEXR_CAPABLE_FPD = '6.0.0'


XR_CONFIG_NAME_IN_CSM = "xr.cfg"
xr_config_name_in_csm = "xr.cfg"
BREAKOUT_CONFIG_NAME_IN_CSM = "breakout.cfg"
breakout_config_name_in_csm = "breakout.cfg"
ADMIN_CONFIG_NAME_IN_CSM = "admin.cfg"
admin_config_name_in_csm = "admin.cfg"


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
        match = re.search('Filename[\sA-Za-z\n]*[-\s]*\S*\s+(\d*)\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+(\d*)', nox_output)

        if match:
            if match.group(1) == match.group(2):
                return True

        return False

    def _is_there_unsupported_config(self, nox_output):
        match = re.search('Filename[\sA-Za-z\n]*[-\s]*\S*\s+\d*\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+(\d*)', nox_output)

        if match:
            if match.group(1) != '0':
                return False

        return True

    def _copy_config_to_repo(self, device, repository, filename):
        """
        Back up the configuration of the device in user's selected repository
        """
        cmd = 'copy running-config ' + repository + '/' + filename
        timeout = 600
        device.execute_command(cmd, timeout=60, wait_for_string='?')
        device.execute_command('\r', timeout=60, wait_for_string='?')
        success, output = device.execute_command('\r', timeout=timeout)
        print cmd, '\n', output, "<-----------------", success
        if not re.search('OK', output):
            self.error("failed to copy running-config to your repository. Please check session.log for error and fix the issue.")

    def _upload_files_to_tftp(self, device, sourcefiles, repo_url, destfilenames):
        db_session = DBSession()
        server = db_session.query(Server).filter(Server.server_url == repo_url).first()
        if not server:
            self.error("Cannot map the tftp server url to the tftp server repository. Please check the tftp repository setup on CSM.")

        for x in range(0, len(sourcefiles)):
            try:
                shutil.copy(sourcefiles[x], server.server_directory + os.sep + destfilenames[x])
            except:
                db_session.close()
                self._disconnect_and_raise_error(device, "Exception was thrown while copying file " + sourcefiles[x] + " to " + server.server_directory + os.sep + destfilenames[x])
        db_session.close()
        return True


    def _copy_files_to_device(self, device, repository, source_filenames, dest_files, timeout):

        for x in range(0, len(source_filenames)):
            success, output = device.execute_command('dir ' + dest_files[x])
            cmd = 'copy ' + repository + '/' + source_filenames[x] + ' ' + dest_files[x]
            device.execute_command(cmd, timeout=timeout, wait_for_string='?')

            if "No such file" not in output:
                device.execute_command('\r', timeout=timeout, wait_for_string='?')

            success, output = device.execute_command('\r', timeout=timeout)

            if re.search('[Ee]rror', output):
                self.error("Failed to copy file " + repository + '/' + source_filenames[x] + " to " + dest_files[x] + " to device. Please check session.log.")

    def _disconnect_and_raise_error(self, device, msg):
        device.disconnect()
        self.log(msg)
        raise




    def _take_out_breakout_config(self, device, xr_config_file, breakout_file):
        breakout_config_empty = True
        if not os.path.isfile(xr_config_file):
            self.error("The configuration file we backed up during Pre-Migrate - " + xr_config_file + " - is not found.")
        try:
            classic_config = open(xr_config_file, "r+")
        except:
            self._disconnect_and_raise_error(device, "Exception was thrown when opening file " + xr_config_file + ". Disconnecting...")

        try:
            with open(breakout_file, 'w') as breakout_config:
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
        except:
            self._disconnect_and_raise_error(device, "Exception was thrown when writing file " + breakout_file + ". Disconnecting...")

        if breakout_config_empty:
            os.remove(breakout_file)
        return breakout_config_empty


    def _copy_files_to_csm_data(self, device, repo_url, source_filenames, dest_files):
        db_session = DBSession()
        server = db_session.query(Server).filter(Server.server_url == repo_url).first()
        if not server:
            self.error("Cannot map the tftp server url to the tftp server repository. Please check the tftp repository setup on CSM.")


        for x in range(0, len(source_filenames)):
            try:
                shutil.copy(server.server_directory + os.sep + source_filenames[x], dest_files[x])
            except:
                db_session.close()
                self._disconnect_and_raise_error(device, "Exception was thrown while copying file " + server.server_directory + os.sep + source_filenames[x] + " to " + dest_files[x])

        db_session.close()

    def _post_status(self, msg):
        if self.csm_ctx:
            self.csm_ctx.post_status(msg)

    def _run_migration_on_config(self, device, fileloc, filename, nox_to_use, host_ip):
        commands = [subprocess.Popen(["chmod", "+x", nox_to_use]), subprocess.Popen([nox_to_use, "-f", fileloc + os.sep + filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)]

        nox_output, nox_error = commands[1].communicate()

        if nox_error:
            self.error("Failed to run the configuration migration tool on the admin configuration we retrieved from device - " + nox_error)

        conversion_success = self._is_conversion_successful(nox_output)

        if filename == ADMIN_CONFIG_NAME_IN_CSM:
            supported_log_name = "supported_config_in_admin_configuration"
            unsupported_log_name = "unsupported_config_in_admin_configuration"
        else:
            supported_log_name = "supported_config_in_xr_configuration"
            unsupported_log_name = "unsupported_config_in_xr_configuration"

        if conversion_success:

            if self._is_there_unsupported_config(nox_output):
                self.log("Configuration " + filename + " was migrated successfully. No unsupported configurations found.")
            else:
                self._create_config_logs(device, fileloc + os.sep + filename.split('.')[0] + ".csv", supported_log_name, unsupported_log_name, host_ip, filename)
                self.log("Configuration " + filename + " was migrated successfully, however, please know that we removed some configurations that are unsupported in eXR. Please look into " + unsupported_log_name + " and " + supported_log_name + ".")
        else:
            self._create_config_logs(device, fileloc + os.sep + filename.split('.')[0] + ".csv", supported_log_name, unsupported_log_name, host_ip, filename)

            self.error("The configuration file contains configurations that are unknown to the NoX configuration conversion tool. Please look into " + unsupported_log_name + " for configurations that are unprocessed by the conversion tool. The known or supported configurations are in " + supported_log_name + ". You can see the configurations in both your server repository and locally in " + fileloc + ".")


    def _check_platform(self, device):

        success, output = device.execute_command("admin")

        if success:
            success, output = device.execute_command("show install active")
            if success:
                match = re.search('asr9k-mini-px', output)

                if not match:
                    self.error('Device is not running ASR9K Classic XR asr9k-mini-px image. Migration action aborted.')
            else:
                self.error("Failed to detect active package on device. Please check session.log.")
        else:
            self.error("Failed to enter admin mode. Please check session.log.")

        device.execute_command("exit")

        return True

    def _check_release_version(self, device):

        success, versioninfo = device.execute_command("show version")

        match = re.search('[Vv]ersion\s+?(\d\.\d\.\d)', versioninfo)

        if not match:
            self.error("Failed to recognize release version number. Please check session.log.")

        release_version = match.group(1)

        if release_version < MINIMUM_RELEASE_VERSION_FOR_MIGRATION:
            self.error("The minimal release version required for migration is 5.3.3. Please upgrade to at lease R5.3.3 before scheduling migration.")


    def _ping_repo_check(self, device, repo_str):

        repo_ip = re.search('.*/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/.*', repo_str)

        if not repo_ip:
            self.error("Bad hostname for server repository. Please check the settings in CSM.")

        success, output = device.execute_command("ping " + repo_ip.group(1))
        if "100 percent" not in output:
            self.error("Failed to ping server repository " + repo_ip.group(1) + " on device. Please check session.log.")

    def _resize_eusb(self, device, repository, packages):

        #self._copy_files_to_device(device, repository, ['resize_eusb'], ['disk0:/resize_eusb'], 100)
        device.execute_command('run', wait_for_string='#')
        cmd = 'ksh /pkg/bin/resize_eusb'
        success, output = device.execute_command(cmd, wait_for_string='#')
        device.execute_command('exit')
        if not "eUSB partition completed." in output:
            self.error("eUSB partition failed. Please check session.log.")

        # self._copy_files_to_device(device, repository, ['migrate_to_eXR'], ['harddiskb:/migrate_to_eXR'], 100)



    def _check_fpd(self, device):
        cmd = 'show hw-module fpd location all'
        success, fpdtable = device.execute_command(cmd)

        if not success:
            self.error("Failed to check FPD version before migration")


        # location_to_subtypes_need_upgrade = {}

        # self._find_all_fpds_need_upgrade(fpdtable, ROUTEPROCESSOR_RE, location_to_subtypes_need_upgrade)
        # self._find_all_fpds_need_upgrade(fpdtable, LINECARD_RE, location_to_subtypes_need_upgrade)

        subtypes_need_upgrade = Set([])
        self._find_all_fpds_need_upgrade(fpdtable, ROUTEPROCESSOR_RE, subtypes_need_upgrade)
        self._find_all_fpds_need_upgrade(fpdtable, LINECARD_RE, subtypes_need_upgrade)

        # return location_to_subtypes_need_upgrade
        return subtypes_need_upgrade



    # def _find_all_fpds_need_upgrade(self, fpdtable, location, location_to_subtypes_need_upgrade):
    def _find_all_fpds_need_upgrade(self, fpdtable, location, subtypes_need_upgrade):
        for fpdtype in FPDS_CHECK_FOR_UPGRADE:
            match = re.search(location + '[-.A-Z0-9a-z\s]*?' + fpdtype + '[-.A-Z0-9a-z\s]*?(No|Yes)', fpdtable)

            if match:
                if match.group(2) == "Yes":
                    subtypes_need_upgrade.add(fpdtype)
                    # if not match.group(1) in location_to_subtypes_need_upgrade:
                        # location_to_subtypes_need_upgrade[match.group(1)] = []
                    # location_to_subtypes_need_upgrade[match.group(1)].append(fpdtype)


    def _ensure_updated_fpd(self, device, repo, packages):

        # check for the FPD version, if FPD needs upgrade,
        # enable the FPD Auto Upgrade Feature

        # location_to_subtypes_need_upgrade = self._check_fpd(device)
        subtypes_need_upgrade = self._check_fpd(device)

        # if location_to_subtypes_need_upgrade:
        if subtypes_need_upgrade:

            cmd = "show install active summary"
            success, active_packages = device.execute_command(cmd)
            print cmd, '\n', active_packages, "<-----------------", success

            match = re.search('fpd', active_packages)

            if not match:
                self.error("Device needs FPD upgrade but no FPD pie is active on device. Please install FPD pie to try again or manually upgrade your FPDs to eXR capable FPDs.")


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
            # self._upgrade_all_fpds(device, location_to_subtypes_need_upgrade)
            self._upgrade_all_fpds(device, subtypes_need_upgrade)


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



    # def _upgrade_all_fpds(self, device, location_to_subtypes_need_upgrade):
    def _upgrade_all_fpds(self, device, subtypes_need_upgrade):

        # for location in location_to_subtypes_need_upgrade:

        #    for fpdtype in location_to_subtypes_need_upgrade[location]:
        for fpdtype in subtypes_need_upgrade:

            # self._post_status("FPD upgrade - start to upgrade FPD subtype " + fpdtype + " in location " + location)
            self._post_status("FPD upgrade - start to upgrade FPD subtype " + fpdtype + " in all locations")
            # command = 'admin upgrade hw-module fpd ' + fpdtype + ' force location ' + location
            command = 'admin upgrade hw-module fpd ' + fpdtype + ' force location all'
            device.execute_command(command, timeout=60, wait_for_string='?')
            print "entered upgrade command"
            success, output = device.execute_command('\r yes', timeout=9600)
            print "entered enter and yes"

            # fpd_upgrade_success = re.search(location + '.*' + fpdtype + '[-_%.A-Z0-9a-z\s]*[Ss]uccess', output)
            fpd_upgrade_success = re.search('[Ss]uccess', output)
            if not fpd_upgrade_success:
                # self.error("Failed to force upgrade FPD subtype " + fpdtype + " in location " + location)
                self.error("Failed to force upgrade FPD subtype " + fpdtype + " in all locations")

        return True


    def _create_config_logs(self, device, csvfile, supported_log_name, unsupported_log_name, host_ip, filename):
        if not self.csm_ctx or not self.csm_ctx.log_directory:
            self.error("Cannot fetch the log directory in csm_ctx from plugin.")

        supported_config_log = self.csm_ctx.log_directory + os.sep + supported_log_name
        unsupported_config_log = self.csm_ctx.log_directory + os.sep + unsupported_log_name
        try:
            with open(supported_config_log, 'w') as supp_log:
                with open(unsupported_config_log, 'w') as unsupp_log:
                    supp_log.write('Configurations Known and Supported to the NoX Conversion Tool \n \n')

                    unsupp_log.write('Configurations Unprocessed by the NoX Conversion Tool (Comments, Markers, or Unknown/Unsupported Configurations) \n \n')

                    supp_log.write('{0[0]:<8} {0[1]:^20}'.format(("Line No.", "Configuration")) + '\n')
                    unsupp_log.write('{0[0]:<8} {0[1]:^20}'.format(("Line No.", "Configuration")) + '\n')
                    with open(csvfile, 'rb') as csvfile:
                        reader = csv.reader(csvfile)
                        for row in reader:
                            if len(row) >= 3 and row[1].strip() == "KNOWN_SUPPORTED":
                                supp_log.write('{0[0]:<8} {0[1]:<}'.format((row[0], row[2])) + '\n')
                            elif len(row) >= 3:
                                unsupp_log.write('{0[0]:<8} {0[1]:<}'.format((row[0], row[2])) + '\n')

                    msg = '\n \nPlease find original configuration ' + filename + ' in csm_data/migration/' + host_ip + '/' + filename + ' \n'
                    supp_log.write(msg)
                    unsupp_log.write(msg)
                    msg2 = 'The final converted configuration is in csm_data/migration/' + host_ip + '/' + filename.split('.')[0] + '.iox'
                    supp_log.write(msg2)
                    unsupp_log.write(msg2)
                    csvfile.close()
                unsupp_log.close()
            supp_log.close()
        except:
            self._disconnect_and_raise_error(device, "Exception was thrown when writing diagnostic files - " + supported_config_log + " and " + unsupported_config_log + " after converting admin configuration using the NoX tool. . Disconnecting...")

    def _handle_configs(self, device, host_ip, repo_str, fileloc, nox_to_use):

        xr_config_name_in_repo = host_ip + "_" + XR_CONFIG_NAME_IN_CSM

        admin_config_name_in_repo = host_ip + "_" + ADMIN_CONFIG_NAME_IN_CSM



        self._post_status("Saving current configuration files on device into server repository and csm_data")
        self._copy_config_to_repo(device, repo_str, xr_config_name_in_repo)


        success, output = device.execute_command('admin')
        if success:
            self._copy_config_to_repo(device, repo_str, admin_config_name_in_repo)
            device.execute_command('exit')


        self._copy_files_to_csm_data(device, repo_str, [xr_config_name_in_repo, admin_config_name_in_repo], [fileloc + os.sep + XR_CONFIG_NAME_IN_CSM, fileloc + os.sep + ADMIN_CONFIG_NAME_IN_CSM])



        self._post_status("Converting admin configuration file with configuration migration tool")
        self._run_migration_on_config(device, fileloc, ADMIN_CONFIG_NAME_IN_CSM, nox_to_use, host_ip)
        #self._run_migration_on_config(device, fileloc, "system.tech", NOX_FOR_MAC)

        self._post_status("Converting IOS-XR configuration file with configuration migration tool")
        self._run_migration_on_config(device, fileloc, XR_CONFIG_NAME_IN_CSM, nox_to_use, host_ip)

        config_files = ["xr.iox", "admin.cal"]

        if not self._take_out_breakout_config(device, fileloc + os.sep + XR_CONFIG_NAME_IN_CSM, fileloc + os.sep + BREAKOUT_CONFIG_NAME_IN_CSM):
            config_files.append(BREAKOUT_CONFIG_NAME_IN_CSM)

        if os.path.isfile(fileloc + os.sep + "admin.iox"):
            config_files.append("admin.iox")

        self._post_status("Uploading the migrated configuration files to server repository and device.")

        config_names_in_repo = [host_ip + "_" + config_name for config_name in config_files]

        if self._upload_files_to_tftp(device, [fileloc + os.sep + config_name for config_name in config_files], repo_str, config_names_in_repo):

            self._copy_files_to_device(device, repo_str, config_names_in_repo, ["harddiskb:/" + config_name for config_name in config_files], TIMEOUT_FOR_COPY_CONFIG)

    def _copy_iso_to_device(self, device, packages, repo_str):
        found_iso = False
        for package in packages:
            if ".iso" in package:
                if package == ISO_FULL_IMAGE_NAME or package == ISO_MINI_IMAGE_NAME:
                    found_iso = True
                    self._copy_files_to_device(device, repo_str, [package], ['harddiskb:/'+ package], TIMEOUT_FOR_COPY_ISO)
                else:
                    self.error("Please make sure that the only ISO image you select on your server repository is asr9k-full-x64.iso. This is the only ISO image supported so far.")


        if not found_iso:
            self.error("Please make sure that you select asr9k-full-x64.iso on your server repository. This ISO image is required for migration.")

    def _find_nox_to_use(self):

        check_32_or_64_system = subprocess.Popen(['uname', '-a'], stdout=subprocess.PIPE)

        out, err = check_32_or_64_system.communicate()

        if err:
            print(err)
            raise PluginError("Error when trying to use 'uname -a' to determine if the linux system you are hosting CSM on is 32 bit or 64 bit.")

        if "x86_64" in out:
            return NOX_64_BINARY
        else:
            return NOX_32_BINARY




    def start(self, device, *args, **kwargs):

        repo_str = kwargs.get('repository', None)

        packages = kwargs.get("pkg_file", None)
        if not packages:
            packages = []

        host_directory_name = device.name.strip().replace('.', '_').replace(':','-')

        fileloc = get_migration_directory() + host_directory_name

        self.log(self.NAME + " Plugin is running")


        self._post_status("Checking if migration requirements are met.")
        self._check_platform(device)
        self._check_release_version(device)
        self._ping_repo_check(device, repo_str)

        node_status = NodeStatusPlugin()
        try:
            node_status.start(device)
        except PluginError:
            raise PluginError("Not all nodes are in valid IOS-XR final states. Pre-Migrate fails. Please check session.log to trouble-shoot.")

        self._post_status("Resizing eUSB partition.")
        self._resize_eusb(device, repo_str, packages)


        nox_to_use = get_migration_directory() + self._find_nox_to_use()

        nox_to_use = get_migration_directory() + NOX_FOR_MAC

        if not os.path.isfile(nox_to_use):
            print nox_to_use
            self.error("The configuration conversion tool " + nox_to_use + " is missing. CSM should have downloaded it when this migration action was scheduled.")
        self._handle_configs(device, host_directory_name, repo_str, fileloc, nox_to_use)

        self._post_status("Copying the eXR ISO image from server repository to device.")
        self._copy_iso_to_device(device, packages, repo_str)


        self._post_status("Checking FPD version...")
        self._ensure_updated_fpd(device, repo_str, packages)


        return True

