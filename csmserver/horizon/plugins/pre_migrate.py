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
import sys

import os
import subprocess
import re
import requests
import shutil
import csv
from database import DBSession
from models import Server


from horizon.plugin import PluginError, Plugin

from horizon.plugins.install_add import InstallAddPlugin
from horizon.plugins.install_activate import InstallActivatePlugin
from horizon.plugins.install_commit import InstallCommitPlugin
from horizon.plugins.node_status.asr9k.node_status import NodeStatusPlugin
from horizon.package_lib import parse_xr_show_platform, validate_xr_node_state

from condoor import TIMEOUT


MINIMUM_RELEASE_VERSION_FOR_MIGRATION = "5.3.3"

#NOX_64_BINARY = "nox_linux_64bit_6.0.0v3.bin"
NOX_64_BINARY = "nox-linux-64.bin"
NOX_32_BINARY = "nox_linux_32bit_6.0.0v3.bin"
NOX_FOR_MAC = "nox-mac64"

TIMEOUT_FOR_COPY_CONFIG = 3600
TIMEOUT_FOR_COPY_ISO = 3600
TIMEOUT_FOR_FPD_UPGRADE = 9600

ISO_FULL_IMAGE_NAME = "asr9k-full-x64.iso"
ISO_MINI_IMAGE_NAME = "asr9k-mini-x64.iso"
ISO_LOCATION = "harddiskb:/"


ROUTEPROCESSOR_RE = '(\d+/RS??P\d(?:/CPU\d*)?)'
#LINECARD_RE = '[-\s](\d+/\d+(?:/CPU\d*)?)'

SUPPORTED_CARDS = ['4X100', '8X100', '12X100']

#NODE = '[-|\s](\d+/(?:RS?P)?\d+/CPU\d+)'
NODE = '(\d+/(?:RS?P)?\d+/CPU\d+)'

#FPDS_CHECK_FOR_UPGRADE = set(['cbc', 'rommon', 'fpga2', 'fsbl', 'lnxfw', 'fpga8', 'fclnxfw', 'fcfsbl'])
FPDS_CHECK_FOR_UPGRADE = set(['fpga2'])

MINIMUM_RELEASE_VERSION_FOR_FLEXR_CAPABLE_FPD = '6.0.1'


XR_CONFIG_IN_CSM = "xr.cfg"
BREAKOUT_CONFIG_IN_CSM = "breakout.cfg"
ADMIN_CONFIG_IN_CSM = "admin.cfg"

CONVERTED_XR_CONFIG_IN_CSM = "xr.iox"
CONVERTED_ADMIN_CAL_CONFIG_IN_CSM = "admin.cal"
CONVERTED_ADMIN_XR_CONFIG_IN_CSM = "admin.iox"

XR_CONFIG_ON_DEVICE = "iosxr.cfg"
ADMIN_CAL_CONFIG_ON_DEVICE = "admin_calvados.cfg"
ADMIN_XR_CONFIG_ON_DEVICE = "admin_iosxr.cfg"

class PreMigratePlugin(Plugin):

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

    @staticmethod
    def _ping_repository_check(manager, device, repo_url):
        repo_ip = re.search(".*/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/.*", repo_url)

        if not repo_ip:
            manager.error("Bad hostname for server repository. Please check the settings in CSM.")

        output = device.send("ping {}".format(repo_ip.group(1)))
        if "100 percent" not in output:
            manager.error("Failed to ping server repository {} on device. Please check session.log.".format(repo_ip.group(1)))

    @staticmethod
    def _get_iosxr_run_nodes(manager, device):
        iosxr_run_nodes = []
        output = device.send("show platform")
        inventory = parse_xr_show_platform(output)
        node_pattern = re.compile(NODE)
        rp_pattern = re.compile(ROUTEPROCESSOR_RE)
        for key, value in inventory.items():
            if node_pattern.match(key):
                # If this is RSP/RP
                if rp_pattern.match(key):
                    iosxr_run_nodes.append(key)
                # If this is line card
                else:
                    if value['state'] == 'IOS XR RUN':
                        for card in SUPPORTED_CARDS:
                            if card in value['type']:
                                iosxr_run_nodes.append(key)
                                break

        print "iosxr_run_nodes = " + str(iosxr_run_nodes)
        return iosxr_run_nodes


    @staticmethod
    def _is_there_unsupported_config(nox_output):
        match = re.search("Filename[\sA-Za-z\n]*[-\s]*\S*\s+\d*\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+(\d*)", nox_output)

        if match:
            if match.group(1) != "0":
                return False

        return True

    @staticmethod
    def _copy_config_to_repo(manager, device, repository, filename, admin=""):
        """
        Back up the configuration of the device in user's selected repository
        """

        def send_newline(ctx):
            ctx.ctrl.sendline()
            return True

        def error(ctx):
            ctx.message = "nvgen error"
            return False

        """
        if admin:
            cmd = 'admin copy running-config ' + repository + '/' + filename
        else:
            cmd = 'copy running-config ' + repository + '/' + filename

        device.send(cmd, timeout=60, wait_for_string='\?')
        output = device.send('\r', timeout=60, wait_for_string='\?')
        print "copy running-config output1 = " + output
        output = device.send('\r', timeout=600)
        print "copy running-config output2 = " + output
        """
        command = "{}copy running-config {}/{}".format(admin, repository, filename)

        CONFIRM_IP = re.compile("Host name or IP address.*\?")
        CONFIRM_FILENAME = re.compile("Destination file name.*\?")
        OK = re.compile(".*\s*\[OK\]")
        FILE_EXISTS = re.compile("nvgen:.*\sFile exists")

        events = [device.prompt, CONFIRM_IP, CONFIRM_FILENAME, OK, TIMEOUT, FILE_EXISTS]
        transitions = [
            (CONFIRM_IP, [0], 1, send_newline, 0),
            (CONFIRM_FILENAME, [1], 2, send_newline, TIMEOUT_FOR_COPY_CONFIG),
            (OK, [2], 3, None, 10),
            (device.prompt, [3], -1, None, 0),
            (TIMEOUT, [0, 1, 2, 3], 4, None, 0),
            (FILE_EXISTS, [2], 4, error, 0)
        ]
        manager.log("Copying {}configuration on device to {}".format(admin, repository))
        if not device.run_fsm(PreMigratePlugin.DESCRIPTION, command, events, transitions, timeout=20):
            manager.error("Failed to copy running-config to your repository. Please check session.log for error and fix the issue.")
            return False
        """
        if not re.search('OK', output):
            if re.search('File exists', output):
                manager.error("Failed to copy running-config to your repository. File " + filename + " already exists in your tftp repository " + repository + ". Possible solution: rename or delete the file. ")
            else:

                manager.error("Failed to copy running-config to your repository. Please check session.log for error and fix the issue.")
        """

    @staticmethod
    def _upload_files_to_tftp(manager, device, sourcefiles, repo_url, destfilenames):
        db_session = DBSession()
        server = db_session.query(Server).filter(Server.server_url == repo_url).first()
        if not server:
            manager.error("Cannot map the tftp server url to the tftp server repository. Please check the tftp repository setup on CSM.")

        for x in range(0, len(sourcefiles)):
            try:
                shutil.copy(sourcefiles[x], server.server_directory + os.sep + destfilenames[x])
            except:
                db_session.close()
                PreMigratePlugin._disconnect_and_raise_error(manager, device, "Exception was thrown while copying file {} to {}/{}.".format(sourcefiles[x], server.server_directory, destfilenames[x]))
        db_session.close()
        return True


    @staticmethod
    def _copy_files_to_device(manager, device, repository, source_filenames, dest_files, timeout=600):

        def send_newline(ctx):
            ctx.ctrl.sendline()
            return True


        def error(ctx):
            ctx.message = "Error copying file. No such file or directory in server repository."
            return False

        for x in range(0, len(source_filenames)):

            """
            cmd = 'copy ' + repository + '/' + source_filenames[x] + ' ' + dest_files[x]
            device.send(cmd, timeout=timeout, wait_for_string='\?')

            if "No such file" not in output:
                device.send('\r', timeout=timeout, wait_for_string='\?')

            output = device.send('\r', timeout=timeout)

            if re.search('copied in', output):
                return True
            else:
                manager.error("Failed to copy file " + repository + '/' + source_filenames[x] + " to " + dest_files[x] + " to device. Please check session.log.")
            """
            command = "copy {}/{} {}".format(repository, source_filenames[x], dest_files[x])

            CONFIRM_FILENAME = re.compile("Destination filename.*\?")
            CONFIRM_OVERWRITE = re.compile("Copy : Destination exists, overwrite \?\[confirm\]")
            COPIED = re.compile(".+bytes copied in.+ sec")
            NO_SUCH_FILE = re.compile("%Error copying.*\(Error opening source file\): No such file or directory")

            events = [device.prompt, CONFIRM_FILENAME, CONFIRM_OVERWRITE, COPIED, TIMEOUT, NO_SUCH_FILE]
            transitions = [
                (CONFIRM_FILENAME, [0], 1, send_newline, timeout),
                (CONFIRM_OVERWRITE, [1], 2, send_newline, timeout),
                (COPIED, [1, 2], 3, None, 20),
                (device.prompt, [3], -1, None, 0),
                (TIMEOUT, [0, 1, 2, 3], 4, None, 0),
                (NO_SUCH_FILE, [0, 1, 2, 3], 4, error, 0)
            ]
            manager.log("Copying {}/{} to {} on device".format(repository, source_filenames[x], dest_files[x]))
            if not device.run_fsm(PreMigratePlugin.DESCRIPTION, command, events, transitions, timeout=20):
                manager.error("Error copying {}/{} to {} on device".format(repository, source_filenames[x], dest_files[x]))

            output = device.send("dir {}".format(dest_files[x]))
            if "No such file" in output:
                manager.error("Failed to copy {}/{} to {} on device".format(repository, source_filenames[x], dest_files[x]))
    @staticmethod
    def _disconnect_and_raise_error(manager, device, msg):
        device.disconnect()
        manager.error(msg)


    @staticmethod
    def _copy_files_to_csm_data(manager, device, repo_url, source_filenames, dest_files):
        db_session = DBSession()
        server = db_session.query(Server).filter(Server.server_url == repo_url).first()
        if not server:
            manager.error("Cannot map the tftp server url to the tftp server repository. Please check the tftp repository setup on CSM.")


        for x in range(0, len(source_filenames)):
            try:
                shutil.copy(server.server_directory + os.sep + source_filenames[x], dest_files[x])
            except:
                db_session.close()
                PreMigratePlugin._disconnect_and_raise_error(manager, device, "Exception was thrown while copying file {}/{} to {}.".format(server.server_directory, source_filenames[x], dest_files[x]))

        db_session.close()


    @staticmethod
    def _run_migration_on_config(manager, device, fileloc, filename, nox_to_use, hostname):
        commands = [subprocess.Popen(["chmod", "+x", nox_to_use]), subprocess.Popen([nox_to_use, "-f", fileloc + os.sep + filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)]

        nox_output, nox_error = commands[1].communicate()

        if nox_error:
            manager.error("Failed to run the configuration migration tool on the admin configuration we retrieved from device - {}.".format(nox_error))

        conversion_success = False

        match = re.search("Filename[\sA-Za-z\n]*[-\s]*\S*\s+(\d*)\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+(\d*)", nox_output)

        if match:
            if match.group(1) == match.group(2):
                conversion_success = True

        if filename == ADMIN_CONFIG_IN_CSM:
            supported_log_name = "supported_config_in_admin_configuration"
            unsupported_log_name = "unsupported_config_in_admin_configuration"
        else:
            supported_log_name = "supported_config_in_xr_configuration"
            unsupported_log_name = "unsupported_config_in_xr_configuration"

        if conversion_success:

            if PreMigratePlugin._is_there_unsupported_config(nox_output):
                manager.log("Configuration {} was migrated successfully. No unsupported configurations found.".format(filename))
            else:
                PreMigratePlugin._create_config_logs(manager, device, fileloc + os.sep + filename.split(".")[0] + ".csv", supported_log_name, unsupported_log_name, hostname, filename)
                manager.log("Configurations that are unsupported in eXR were removed in {}. Please look into {} and {}.".format(filename, unsupported_log_name, supported_log_name))
        else:
            PreMigratePlugin._create_config_logs(manager, device, fileloc + os.sep + filename.split(".")[0] + ".csv", supported_log_name, unsupported_log_name, hostname, filename)

            manager.error("Unknown configurations found. Please look into {} for unprocessed configurations, and {} for known/supported configurations".format(unsupported_log_name, supported_log_name))



    @staticmethod
    def _resize_eusb(manager, device):
        device.send("run", wait_for_string="#")
        output = device.send("ksh /pkg/bin/resize_eusb", wait_for_string="#")
        device.send("exit")
        if not "eUSB partition completed." in output:
            manager.error("eUSB partition failed. Please check session.log.")



    @staticmethod
    def _check_fpd(device, iosxr_run_nodes):
        fpdtable = device.send("show hw-module fpd location all")

        subtype_to_locations_need_upgrade = {}

        for fpdtype in FPDS_CHECK_FOR_UPGRADE:
            match_iter = re.finditer(NODE + "[-.A-Z0-9a-z\s]*?" + fpdtype + "[-.A-Z0-9a-z\s]*?(No|Yes)", fpdtable)

            for match in match_iter:
                if match.group(1) in iosxr_run_nodes:
                    if match.group(2) == "Yes":
                        if not fpdtype in subtype_to_locations_need_upgrade:
                            subtype_to_locations_need_upgrade[fpdtype] = []
                        subtype_to_locations_need_upgrade[fpdtype].append(match.group(1))

        return subtype_to_locations_need_upgrade




    @staticmethod
    def _ensure_updated_fpd(manager, device, packages, iosxr_run_nodes):

        manager.log("Checking if FPD package is present...")
        active_packages = device.send("show install active summary")

        match = re.search("fpd", active_packages)

        if not match:
            manager.error("No FPD pie is active on device. Please install FPD pie to try again or manually upgrade your FPDs to eXR capable FPDs.")

        versioninfo = device.send("show version")

        match = re.search("[Vv]ersion\s+?(\d\.\d\.\d)", versioninfo)

        if not match:
            manager.error("Failed to recognize release version number. Please check session.log.")

        release_version = match.group(1)

        if release_version < MINIMUM_RELEASE_VERSION_FOR_FLEXR_CAPABLE_FPD:

            manager.log("Checking if FPD SMU has been installed...")
            pie_packages = []
            for package in packages:
                if package.find(".pie") > -1:
                    pie_packages.append(package)

            if len(pie_packages) != 1:
                manager.error("Please select exactly one FPD SMU pie on server repository for FPD upgrade. The filename must end with '.pie'")

            name_of_fpd_smu = pie_packages[0].split(".pie")[0]

            install_summary = device.send("show install active summary")

            match = re.search(name_of_fpd_smu, install_summary)

            if not match:

                #Step 1: Install add the FPD SMU
                manager.log("FPD upgrade - install add the FPD SMU...")
                PreMigratePlugin._run_install_action_plugin(manager, device, InstallAddPlugin, "install add")

                #Step 2: Install activate the FPD SMU
                manager.log("FPD upgrade - install activate the FPD SMU...")
                PreMigratePlugin._run_install_action_plugin(manager, device, InstallActivatePlugin, "install activate")


                #Step 3: Install commit the FPD SMU
                manager.log("FPD upgrade - install commit the FPD SMU...")
                PreMigratePlugin._run_install_action_plugin(manager, device, InstallCommitPlugin, "install commit")

            else:
                manager.log("The selected FPD SMU {} is found already active on device.".format(pie_packages[0]))

        # check for the FPD version, if FPD needs upgrade,
        manager.log("Checking FPD version...")
        subtype_to_locations_need_upgrade = PreMigratePlugin._check_fpd(device, iosxr_run_nodes)

        print "subtype_to_locations_need_upgrade = " + str(subtype_to_locations_need_upgrade)

        if subtype_to_locations_need_upgrade:

            """
            Force upgrade all fpds in RP and Line card that need upgrade, with the FPD pie or both the FPD pie and FPD SMU depending on release version
            """
            PreMigratePlugin._upgrade_all_fpds(manager, device, subtype_to_locations_need_upgrade)


        return True

    @staticmethod
    def _run_install_action_plugin(manager, device, install_plugin, install_action_name):
        try:
            install_plugin.start(manager, device)
        except PluginError as e:
            manager.error("Failed to {} the FPD SMU - ({}): {}".format(install_action_name, e.errno, e.strerror))
        except AttributeError:
            device.disconnect()
            manager.log("Disconnected...")
            raise PluginError("Failed to {} the FPD SMU. Please check session.log for details of failure.".format(install_action_name))


    @staticmethod
    def _upgrade_all_fpds(manager, device, subtype_to_locations_need_upgrade):

        def send_newline(ctx):
            ctx.ctrl.sendline()
            return True

        def send_yes(ctx):
            ctx.ctrl.sendline("yes")
            return True

        for fpdtype in subtype_to_locations_need_upgrade:

            manager.log("FPD upgrade - start to upgrade FPD {} on all locations".format(fpdtype))
            """
            device.send("admin upgrade hw-module fpd " + fpdtype + " force location all", timeout=60, wait_for_string='\?')
            output = device.send('\r yes', timeout=9600)

            fpd_upgrade_success = re.search('[Ss]uccess', output)
            if not fpd_upgrade_success:
                manager.error("Failed to force upgrade FPD subtype " + fpdtype + " in all locations")
            """


            CONFIRM_CONTINUE = re.compile("Continue\? \[confirm\]")
            CONFIRM_SECOND_TIME = re.compile("Continue \? \[no\]:")
            #IN_PROGRESS = re.compile("FPD upgrade in progress.")
            #SUCCESS = re.compile(".*Successfully (?:downgraded|upgraded).+{}".format(location))
            #FAIL = re.compile("FPD upgrade execution failed")
            UPGRADE_END = re.compile("FPD upgrade has ended.")

            events = [device.prompt, CONFIRM_CONTINUE, CONFIRM_SECOND_TIME, UPGRADE_END, TIMEOUT]
            transitions = [
                (CONFIRM_CONTINUE, [0], 1, send_newline, TIMEOUT_FOR_FPD_UPGRADE),
                (CONFIRM_SECOND_TIME, [1], 2, send_yes, TIMEOUT_FOR_FPD_UPGRADE),
                #(IN_PROGRESS, [1, 2], 2, None, 5400),
                #(SUCCESS, [1, 2], 3, None, 120),
                #(FAIL, [1, 2, 3], 5, None, 120),
                #(UPGRADE_END, [3], 4, None, 120),
                #(UPGRADE_END, [2], 5, None, 10),
                (UPGRADE_END, [1, 2], 3, None, 120),
                (device.prompt, [3], -1, None, 0),
                (device.prompt, [1, 2], 5, None, 5),
                (TIMEOUT, [0, 1, 2], 5, None, 20),

            ]

            if not device.run_fsm(PreMigratePlugin.DESCRIPTION, "admin upgrade hw-module fpd {} force location all".format(fpdtype), events, transitions, timeout=30):
                manager.error("Error while upgrading FPD subtype {}. Please check session.log".format(fpdtype))

            fpd_log = device.send("show log | include fpd")

            for location in subtype_to_locations_need_upgrade[fpdtype]:
                fpd_upgrade_success = re.search("Successfully\s*(?:downgrade|upgrade)\s*{}.*location\s*{}".format(fpdtype, location), fpd_log)
                if not fpd_upgrade_success:
                    manager.error("Failed to upgrade FPD subtype {} on location {}. Please check session.log.".format(fpdtype, location))



        return True

    @staticmethod
    def _create_config_logs(manager, device, csvfile, supported_log_name, unsupported_log_name, hostname, filename):

        supported_config_log = manager.csm.log_directory + os.sep + supported_log_name
        unsupported_config_log = manager.csm.log_directory + os.sep + unsupported_log_name
        try:
            with open(supported_config_log, 'w') as supp_log:
                with open(unsupported_config_log, 'w') as unsupp_log:
                    supp_log.write('Configurations Known and Supported to the NoX Conversion Tool \n \n')

                    unsupp_log.write('Configurations Unprocessed by the NoX Conversion Tool (Comments, Markers, or Unknown/Unsupported Configurations) \n \n')

                    supp_log.write('{0[0]:<8} {0[1]:^20} \n'.format(("Line No.", "Configuration")))
                    unsupp_log.write('{0[0]:<8} {0[1]:^20} \n'.format(("Line No.", "Configuration")))
                    with open(csvfile, 'rb') as csvfile:
                        reader = csv.reader(csvfile)
                        for row in reader:
                            if len(row) >= 3 and row[1].strip() == "KNOWN_SUPPORTED":
                                supp_log.write('{0[0]:<8} {0[1]:<} \n'.format((row[0], row[2])))
                            elif len(row) >= 3:
                                unsupp_log.write('{0[0]:<8} {0[1]:<} \n'.format((row[0], row[2])))

                    msg = "\n \nPlease find original configuration in csm_data/migration/{}/{} \n".format(hostname, filename)
                    supp_log.write(msg)
                    unsupp_log.write(msg)
                    if filename.split('.')[0] == 'admin':
                        msg2 = "The final converted configuration is in csm_data/migration/{}/{} and csm_data/migration/{}/{}".format(hostname, CONVERTED_ADMIN_CAL_CONFIG_IN_CSM, hostname, CONVERTED_ADMIN_XR_CONFIG_IN_CSM)
                    else:
                        msg2 = "The final converted configuration is in csm_data/migration/{}/{}".format(hostname, CONVERTED_XR_CONFIG_IN_CSM)
                    supp_log.write(msg2)
                    unsupp_log.write(msg2)
                    csvfile.close()
                unsupp_log.close()
            supp_log.close()
        except Exception as inst:
            print("Oops here is an error occurred~~~~")
            print(type(inst))
            print(inst.args)
            print(inst)
            PreMigratePlugin._disconnect_and_raise_error(manager, device, "Error writing diagnostic files - in {} during configuration migration.".format(manager.csm.log_directory))

    @staticmethod
    def _handle_configs(manager, device, hostname, repo_url, fileloc, nox_to_use, config_filename):

        xr_config_name_in_repo = hostname + "_" + XR_CONFIG_IN_CSM

        admin_config_name_in_repo = hostname + "_" + ADMIN_CONFIG_IN_CSM

        manager.log("Saving the current configurations on device into server repository and csm_data")
        PreMigratePlugin._copy_config_to_repo(manager, device, repo_url, xr_config_name_in_repo)

        PreMigratePlugin._copy_config_to_repo(manager, device, repo_url, admin_config_name_in_repo, admin="admin ")

        PreMigratePlugin._copy_files_to_csm_data(manager, device, repo_url, [xr_config_name_in_repo, admin_config_name_in_repo], [fileloc + os.sep + XR_CONFIG_IN_CSM, fileloc + os.sep + ADMIN_CONFIG_IN_CSM])

        manager.log("Converting admin configuration file with configuration migration tool")
        PreMigratePlugin._run_migration_on_config(manager, device, fileloc, ADMIN_CONFIG_IN_CSM, nox_to_use, hostname)
        #self._run_migration_on_config(device, fileloc, "system.tech", NOX_FOR_MAC)

        # ["admin.cal"]
        config_files = [CONVERTED_ADMIN_CAL_CONFIG_IN_CSM]
        # ["admin_calvados.cfg"]
        config_names_on_device = [ADMIN_CAL_CONFIG_ON_DEVICE]
        if not config_filename:

            manager.log("Converting IOS-XR configuration file with configuration migration tool")
            PreMigratePlugin._run_migration_on_config(manager, device, fileloc, XR_CONFIG_IN_CSM, nox_to_use, hostname)

            # "xr.iox"
            config_files.append(CONVERTED_XR_CONFIG_IN_CSM)
            # "iosxr.cfg"
            config_names_on_device.append(XR_CONFIG_ON_DEVICE)

        # admin.iox
        if os.path.isfile(fileloc + os.sep + CONVERTED_ADMIN_XR_CONFIG_IN_CSM):
            config_files.append(CONVERTED_ADMIN_XR_CONFIG_IN_CSM)
            config_names_on_device.append(ADMIN_XR_CONFIG_ON_DEVICE)

        manager.log("Uploading the migrated configuration files to server repository and device.")

        config_names_in_repo = [hostname + "_" + config_name for config_name in config_files]


        if PreMigratePlugin._upload_files_to_tftp(manager, device, [fileloc + os.sep + config_name for config_name in config_files], repo_url, config_names_in_repo):

            if config_filename:
                config_names_in_repo.append(config_filename)
                # iosxr.cfg
                config_names_on_device.append(XR_CONFIG_ON_DEVICE)

            PreMigratePlugin._copy_files_to_device(manager, device, repo_url, config_names_in_repo, [ISO_LOCATION + config_name for config_name in config_names_on_device], timeout=TIMEOUT_FOR_COPY_CONFIG)

    @staticmethod
    def _copy_iso_to_device(manager, device, packages, repo_url):
        found_iso = False
        for package in packages:
            if ".iso" in package:
                if found_iso == False and (package == ISO_FULL_IMAGE_NAME or package == ISO_MINI_IMAGE_NAME):
                    found_iso = True
                    PreMigratePlugin._copy_files_to_device(manager, device, repo_url, [package], [ISO_LOCATION + package], timeout=TIMEOUT_FOR_COPY_ISO)
                else:
                    manager.error("Please make sure that the only ISO image you select on your server repository is {} or {}.".format(ISO_FULL_IMAGE_NAME, ISO_MINI_IMAGE_NAME))

        if not found_iso:
            manager.error("Please make sure that you select {} or {} on your server repository. This ISO image is required for migration.".format(ISO_FULL_IMAGE_NAME, ISO_MINI_IMAGE_NAME))

    @staticmethod
    def _find_nox_to_use():

        check_32_or_64_system = subprocess.Popen(['uname', '-a'], stdout=subprocess.PIPE)

        out, err = check_32_or_64_system.communicate()

        if err:
            print(err)
            raise PluginError("Failed to execute 'uname -a' to determine if the linux system that CSM is hosted on is 32 bit or 64 bit.")

        if "x86_64" in out:
            return NOX_64_BINARY
        else:
            return NOX_32_BINARY



    @staticmethod
    def start(manager, device, *args, **kwargs):

        """

        server_repo_url = None
        try:
            server_repo_url = manager.csm.server_repository_url
        except AttributeError:
            pass

        if server_repo_url is None:
            manager.error("No repository provided.")

        try:
            packages = manager.csm.software_packages
        except AttributeError:
            manager.error("No package list provided")

        try:
            config_filename = manager.csm.pre_migrate_config_filename
        except AttributeError:
            pass

        host_directory_name = manager.csm.host.hostname

        fileloc = manager.csm.migration_directory + host_directory_name

        if not os.path.exists(fileloc):
            os.makedirs(fileloc)

        manager.log("packages = " + str(packages))


        manager.log("Checking if migration requirements are met.")

        if device.os_type != "XR":
            manager.error('Device is not running ASR9K Classic XR. Migration action aborted.')

        if device.os_version < MINIMUM_RELEASE_VERSION_FOR_MIGRATION:
            manager.error("The minimal release version required for migration is 5.3.3. Please upgrade to at lease R5.3.3 before scheduling migration.")

        PreMigratePlugin._ping_repository_check(manager, device, server_repo_url)

        try:
            NodeStatusPlugin.start(manager, device)
        except PluginError:
            manager.error("Not all nodes are in correct states. Pre-Migrate aborted. Please check session.log to trouble-shoot.")


        iosxr_run_nodes = PreMigratePlugin._get_iosxr_run_nodes(manager, device)


        manager.log("Resizing eUSB partition.")
        PreMigratePlugin._resize_eusb(manager, device)


        nox_to_use = manager.csm.migration_directory + PreMigratePlugin._find_nox_to_use()

        nox_to_use = manager.csm.migration_directory + NOX_FOR_MAC

        if not os.path.isfile(nox_to_use):
            manager.error("The configuration conversion tool {} is missing. CSM should have downloaded it from CCO when migration actions were scheduled.".format(nox_to_use))

        print "fileloc = " + fileloc
        PreMigratePlugin._handle_configs(manager, device, host_directory_name, server_repo_url, fileloc, nox_to_use, config_filename)



        manager.log("Copying the eXR ISO image from server repository to device.")
        PreMigratePlugin._copy_iso_to_device(manager, device, packages, server_repo_url)



        PreMigratePlugin._ensure_updated_fpd(manager, device, packages, iosxr_run_nodes)
        """

        return True

