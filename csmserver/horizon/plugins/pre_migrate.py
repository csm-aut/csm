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

import csv
import os
import re
import subprocess

from condoor import TIMEOUT
from constants import ServerType
from database import DBSession
from horizon.package_lib import parse_xr_show_platform, validate_xr_node_state
from horizon.plugin import PluginError, Plugin
from horizon.plugins.install_add import InstallAddPlugin
from horizon.plugins.install_activate import InstallActivatePlugin
from horizon.plugins.install_commit import InstallCommitPlugin
from horizon.plugins.node_status.asr9k.node_status import NodeStatusPlugin
from models import Server
import pexpect
from server_helper import TFTPServer, FTPServer, SFTPServer
from utils import is_empty, concatenate_dirs

MINIMUM_RELEASE_VERSION_FOR_MIGRATION = "5.3.3"
RELEASE_VERSION_DOES_NOT_NEED_FPD_SMU = "6.1.1"

NOX_64_BINARY = "nox-linux-64.bin"
# NOX_32_BINARY = "nox_linux_32bit_6.0.0v3.bin"
# NOX_FOR_MAC = "nox-mac64"

TIMEOUT_FOR_COPY_CONFIG = 3600
TIMEOUT_FOR_COPY_ISO = 960
TIMEOUT_FOR_FPD_UPGRADE = 9600

ISO_FULL_IMAGE_NAME = "asr9k-full-x64.iso"
ISO_MINI_IMAGE_NAME = "asr9k-mini-x64.iso"
ISO_LOCATION = "harddiskb:/"

ROUTEPROCESSOR_RE = '(\d+/RS??P\d(?:/CPU\d*)?)'
# LINECARD_RE = '[-\s](\d+/\d+(?:/CPU\d*)?)'
SUPPORTED_CARDS = ['4X100', '8X100', '12X100']
NODE = '(\d+/(?:RS?P)?\d+/CPU\d+)'

FPDS_CHECK_FOR_UPGRADE = set(['cbc', 'rommon', 'fpga2', 'fsbl', 'lnxfw', 'fpga8', 'fclnxfw', 'fcfsbl'])

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
    A plugin for preparing device for migration from
    ASR9K IOS-XR (a.k.a. XR) to ASR9K IOS-XR 64 bit (a.k.a. eXR)

    This plugin does the following:
    1. Check several pre-requisites
    2. Resize the eUSB partition(/harddiskb:/ on XR)
    3. Migrate the configurations with NoX and upload them to device
    4. Copy the eXR image to /harddiskb:/
    5. Upgrade some FPD's if needed.

    Console access is needed.
    """

    NAME = "PRE_MIGRATE"
    DESCRIPTION = "PRE-MIGRATE FOR XR TO EXR MIGRATION"
    TYPE = "PRE_MIGRATE"
    VERSION = "0.0.1"

    @staticmethod
    def _ping_repository_check(manager, device, repo_url):
        """Test ping server repository ip from device"""
        repo_ip = re.search("[/@](\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/", repo_url)

        if not repo_ip:
            manager.error("Bad hostname for server repository. Please check the settings in CSM.")

        output = device.send("ping {}".format(repo_ip.group(1)))
        if "100 percent" not in output:
            manager.error("Failed to ping server repository {} on device." +
                          "Please check session.log.".format(repo_ip.group(1)))

    @staticmethod
    def _get_iosxr_run_nodes(manager, device):
        """Get names of all RSP's, RP's and all tomahawk Linecards that are in IOS-XR state"""
        iosxr_run_nodes = []
        cmd = "show platform"
        output = device.send(cmd)
        file_name = manager.file_name_from_cmd(cmd)
        full_name = manager.save_to_file(file_name, output)
        if full_name:
            manager.save_data(cmd, full_name)

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

        return iosxr_run_nodes

    @staticmethod
    def _all_configs_supported(nox_output):
        """Check text output from running NoX on system. Only return True if all configs are supported by eXR."""
        pattern = "Filename[\sA-Za-z\n]*[-\s]*\S*\s+\d*\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+(\d*)"
        match = re.search(pattern, nox_output)

        if match:
            if match.group(1) != "0":
                return False

        return True

    @staticmethod
    def _upload_files_to_server_repository(manager, sourcefiles, server, destfilenames):
        """
        Upload files from their locations in the host linux system to the FTP/TFTP/SFTP server repository.

        Arguments:
        :param manager: the plugin manager
        :param sourcefiles: a list of string file paths that each points to a file on the system where CSM is hosted.
                            The paths are all relative to csm/csmserver/.
                            For example, if the source file is in csm_data/migration/filename,
                            sourcefiles = ["../../csm_data/migration/filename"]
        :param server: the associated server repository object stored in CSM database
        :param destfilenames: a list of string filenames that the source files should be named after being copied to
                              the designated directory in the server repository. i.e., ["thenewfilename"]
        :return: True if no error occurred.
        """

        server_type = server.server_type
        if server_type == ServerType.TFTP_SERVER:
            tftp_server = TFTPServer(server)
            for x in range(0, len(sourcefiles)):
                manager.log("Coping file {} to {}/{}/{}.".format(sourcefiles[x],
                                                                 server.server_directory,
                                                                 manager.csm.install_job.server_directory,
                                                                 destfilenames[x]))
                try:
                    tftp_server.upload_file(sourcefiles[x], destfilenames[x],
                                            sub_directory=manager.csm.install_job.server_directory)
                except:
                    manager.error("Exception was thrown while " +
                                  "copying file {} to {}/{}/{}.".format(sourcefiles[x],
                                                                        server.server_directory,
                                                                        manager.csm.install_job.server_directory,
                                                                        destfilenames[x]))

        elif server_type == ServerType.FTP_SERVER:
            ftp_server = FTPServer(server)
            for x in range(0, len(sourcefiles)):
                manager.log("Coping file {} to {}/{}/{}.".format(sourcefiles[x],
                                                                 server.server_directory,
                                                                 manager.csm.install_job.server_directory,
                                                                 destfilenames[x]))
                try:
                    ftp_server.upload_file(sourcefiles[x], destfilenames[x],
                                           sub_directory=manager.csm.install_job.server_directory)
                except:
                    manager.error("Exception was thrown while " +
                                  "copying file {} to {}/{}/{}.".format(sourcefiles[x],
                                                                        server.server_directory,
                                                                        manager.csm.install_job.server_directory,
                                                                        destfilenames[x]))
        elif server_type == ServerType.SFTP_SERVER:
            sftp_server = SFTPServer(server)
            for x in range(0, len(sourcefiles)):
                manager.log("Coping file {} to {}/{}/{}.".format(sourcefiles[x],
                                                                 server.server_directory,
                                                                 manager.csm.install_job.server_directory,
                                                                 destfilenames[x]))
                try:
                    sftp_server.upload_file(sourcefiles[x], destfilenames[x],
                                            sub_directory=manager.csm.install_job.server_directory)
                except:
                    manager.error("Exception was thrown while " +
                                  "copying file {} to {}/{}/{}.".format(sourcefiles[x],
                                                                        server.server_directory,
                                                                        manager.csm.install_job.server_directory,
                                                                        destfilenames[x]))
        else:
            manager.error("Pre-Migrate does not support {} server repository.".format(server_type))

        return True

    @staticmethod
    def _copy_files_to_device(manager, device, server, repository, source_filenames, dest_files, timeout=600):
        """
        Copy files from their locations in the user selected server directory in the FTP/TFTP/SFTP server repository
        to locations on device.

        Arguments:
        :param manager: the plugin manager
        :param device: the connection to the device
        :param server: the server object fetched from database
        :param repository: the string url link that points to the location of files in the SFTP server repository
        :param source_filenames: a list of string filenames in the designated directory in the server repository.
        :param dest_files: a list of string file paths that each points to a file to be created on device.
                    i.e., ["harddiskb:/asr9k-mini-x64.iso"]
        :param timeout: the timeout for the sftp copy operation on device. The default is 10 minutes.
        :return: None if no error occurred.
        """

        if server.server_type == ServerType.FTP_SERVER or server.server_type == ServerType.TFTP_SERVER:
            PreMigratePlugin._copy_files_from_ftp_tftp_to_device(manager, device, repository,
                                                                 source_filenames, dest_files, timeout=timeout)
        elif server.server_type == ServerType.SFTP_SERVER:

            PreMigratePlugin._copy_files_from_sftp_to_device(manager, device, server,
                                                             source_filenames, dest_files, timeout=timeout)
        else:
            manager.error("Pre-Migrate does not support {} server repository.".format(server.server_type))

    @staticmethod
    def _copy_files_from_ftp_tftp_to_device(manager, device, repository, source_filenames, dest_files, timeout=600):
        """
        Copy files from their locations in the user selected server directory in the FTP or TFTP server repository
        to locations on device.

        Arguments:
        :param manager: the plugin manager
        :param device: the connection to the device
        :param repository: the string url link that points to the location of files in the FTP/TFTP server repository,
                    with no extra '/' in the end. i.e., tftp://223.255.254.245/tftpboot
        :param source_filenames: a list of string filenames in the designated directory in the server repository.
        :param dest_files: a list of string file paths that each points to a file to be created on device.
                    i.e., ["harddiskb:/asr9k-mini-x64.iso"]
        :param timeout: the timeout for the 'copy' CLI command on device. The default is 10 minutes.
        :return: None if no error occurred.
        """

        def send_newline(ctx):
            ctx.ctrl.sendline()
            return True

        def error(ctx):
            ctx.message = "Error copying file."
            return False

        for x in range(0, len(source_filenames)):

            command = "copy {}/{} {}".format(repository, source_filenames[x], dest_files[x])

            CONFIRM_FILENAME = re.compile("Destination filename.*\?")
            CONFIRM_OVERWRITE = re.compile("Copy : Destination exists, overwrite \?\[confirm\]")
            COPIED = re.compile(".+bytes copied in.+ sec")
            NO_SUCH_FILE = re.compile("%Error copying.*\(Error opening source file\): No such file or directory")
            ERROR_COPYING = re.compile("%Error copying")

            events = [device.prompt, CONFIRM_FILENAME, CONFIRM_OVERWRITE, COPIED, TIMEOUT, NO_SUCH_FILE, ERROR_COPYING]
            transitions = [
                (CONFIRM_FILENAME, [0], 1, send_newline, timeout),
                (CONFIRM_OVERWRITE, [1], 2, send_newline, timeout),
                (COPIED, [1, 2], 3, None, 20),
                (device.prompt, [3], -1, None, 0),
                (TIMEOUT, [0, 1, 2, 3], -1, error, 0),
                (NO_SUCH_FILE, [0, 1, 2, 3], -1, error, 0),
                (ERROR_COPYING, [0, 1, 2, 3], -1, error, 0),
            ]

            manager.log("Copying {}/{} to {} on device".format(repository,
                                                               source_filenames[x],
                                                               dest_files[x]))

            if not device.run_fsm(PreMigratePlugin.DESCRIPTION, command, events, transitions, timeout=20):
                manager.error("Error copying {}/{} to {} on device".format(repository,
                                                                           source_filenames[x],
                                                                           dest_files[x]))

            output = device.send("dir {}".format(dest_files[x]))
            if "No such file" in output:
                manager.error("Failed to copy {}/{} to {} on device".format(repository,
                                                                            source_filenames[x],
                                                                            dest_files[x]))

    @staticmethod
    def _copy_files_from_sftp_to_device(manager, device, server, source_filenames, dest_files, timeout=600):
        """
        Copy files from their locations in the user selected server directory in the SFTP server repository
        to locations on device.

        Arguments:
        :param manager: the plugin manager
        :param device: the connection to the device
        :param server: the sftp server object
        :param source_filenames: a list of string filenames in the designated directory in the server repository.
        :param dest_files: a list of string file paths that each points to a file to be created on device.
                    i.e., ["harddiskb:/asr9k-mini-x64.iso"]
        :param timeout: the timeout for the sftp copy operation on device. The default is 10 minutes.
        :return: None if no error occurred.
        """
        source_path = server.server_url

        remote_directory = concatenate_dirs(server.server_directory, manager.csm.install_job.server_directory)
        if not is_empty(remote_directory):
            source_path = source_path + ":{}".format(remote_directory)

        def send_password(ctx):
            ctx.ctrl.sendline(server.password)
            if ctx.ctrl._session.logfile_read:
                ctx.ctrl._session.logfile_read = None
            return True

        def send_yes(ctx):
            ctx.ctrl.sendline("yes")
            if ctx.ctrl._session.logfile_read:
                ctx.ctrl._session.logfile_read = None
            return True

        def reinstall_logfile(ctx):
            if device._session_fd and (not ctx.ctrl._session.logfile_read):
                ctx.ctrl._session.logfile_read = device._session_fd
            else:
                ctx.message = "Error reinstalling session.log."
                return False
            return True

        def error(ctx):
            if device._session_fd and (not ctx.ctrl._session.logfile_read):
                ctx.ctrl._session.logfile_read = device._session_fd
            ctx.message = "Error copying file."
            return False

        for x in range(0, len(source_filenames)):
            if is_empty(server.vrf):
                command = "sftp {}@{}/{} {}".format(server.username, source_path, source_filenames[x], dest_files[x])
            else:
                command = "sftp {}@{}/{} {} vrf {}".format(server.username, source_path, source_filenames[x],
                                                           dest_files[x], server.vrf)

            PASSWORD = re.compile("Password:")
            CONFIRM_OVERWRITE = re.compile("Overwrite.*continue\? \[yes/no\]:")
            COPIED = re.compile("bytes copied in", re.MULTILINE)
            NO_SUCH_FILE = re.compile("src.*does not exist")
            DOWNLOAD_ABORTED = re.compile("Download aborted.")

            events = [device.prompt, PASSWORD, CONFIRM_OVERWRITE, COPIED, TIMEOUT, NO_SUCH_FILE, DOWNLOAD_ABORTED]
            transitions = [
                (PASSWORD, [0], 1, send_password, timeout),
                (CONFIRM_OVERWRITE, [1], 2, send_yes, timeout),
                (COPIED, [1, 2], -1, reinstall_logfile, 0),
                (device.prompt, [1, 2], -1, reinstall_logfile, 0),
                (TIMEOUT, [0, 1, 2], -1, error, 0),
                (NO_SUCH_FILE, [0, 1, 2], -1, error, 0),
                (DOWNLOAD_ABORTED, [0, 1, 2], -1, error, 0),
            ]

            manager.log("Copying {}/{} to {} on device".format(source_path,
                                                               source_filenames[x],
                                                               dest_files[x]))

            if not device.run_fsm(PreMigratePlugin.DESCRIPTION, command, events, transitions, timeout=20):
                manager.error("Error copying {}/{} to {} on device".format(source_path,
                                                                           source_filenames[x],
                                                                           dest_files[x]))

            if device._session_fd and (not device._driver.ctrl._session.logfile_read):
                device._driver.ctrl._session.logfile_read = device._session_fd
            output = device.send("dir {}".format(dest_files[x]))
            if "No such file" in output:
                manager.error("Failed to copy {}/{} to {} on device".format(source_path,
                                                                            source_filenames[x],
                                                                            dest_files[x]))

    @staticmethod
    def _run_migration_on_config(manager, device, fileloc, filename, nox_to_use, hostname):
        """
        Run the migration tool - NoX - on the configurations copied out from device.

        The conversion/migration is successful if the number under 'Total' equals to
        the number under 'Known' in the text output.

        If it's successful, but not all existing configs are supported by eXR, create two
        new log files for the supported and unsupported configs in session log directory.
        The unsupported configs will not appear on the converted configuration files.
        Log a warning about the removal of unsupported configs, but this is not considered
        as error.

        If it's not successful, meaning that there are some configurations not known to
        the NoX tool, in this case, create two new log files for the supported and unsupported
        configs in session log directory. After that, error out.

        :param manager: the plugin manager
        :param device: the connection to the device
        :param fileloc: string location where the config needs to be converted/migrated is,
                        without the '/' in the end. This location is relative to csm/csmserver/
        :param filename: string filename of the config
        :param nox_to_use: string name of NoX binary executable.
        :param hostname: hostname of device, as recorded on CSM.
        :return: None if no error occurred.
        """

        try:
            commands = [subprocess.Popen(["chmod", "+x", nox_to_use]),
                        subprocess.Popen([nox_to_use, "-f", os.path.join(fileloc, filename)],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        ]

            nox_output, nox_error = commands[1].communicate()
        except OSError:
            manager.error("Failed to run the configuration migration tool {} on config file {} - OSError.".format(
                nox_to_use,
                os.path.join(fileloc, filename))
            )

        if nox_error:
            manager.error("Failed to run the configuration migration tool on the admin configuration " +
                          "we retrieved from device - {}.".format(nox_error))

        conversion_success = False

        match = re.search("Filename[\sA-Za-z\n]*[-\s]*\S*\s+(\d*)\s+\d*\(\s*\d*%\)\s+\d*\(\s*\d*%\)\s+(\d*)",
                          nox_output)

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

            if PreMigratePlugin._all_configs_supported(nox_output):
                manager.log("Configuration {} was migrated successfully. ".format(filename) +
                            "No unsupported configurations found.")
            else:
                PreMigratePlugin._create_config_logs(manager,
                                                     os.path.join(fileloc, filename.split(".")[0] + ".csv"),
                                                     supported_log_name, unsupported_log_name,
                                                     hostname, filename)

                manager.log("Configurations that are unsupported in eXR were removed in {}. ".format(filename) +
                            "Please look into {} and {}.".format(unsupported_log_name, supported_log_name))
        else:
            PreMigratePlugin._create_config_logs(manager,
                                                 os.path.join(fileloc, filename.split(".")[0] + ".csv"),
                                                 supported_log_name, unsupported_log_name, hostname, filename)

            manager.error("Unknown configurations found. Please look into {} ".format(unsupported_log_name) +
                          "for unprocessed configurations, and {} for known/supported configurations".format(
                              unsupported_log_name, supported_log_name)
                          )

    @staticmethod
    def _resize_eusb(manager, device):
        """Resize the eUSB partition on device - Run the /pkg/bin/resize_eusb script on device(from ksh)."""
        device.send("run", wait_for_string="#")
        output = device.send("ksh /pkg/bin/resize_eusb", wait_for_string="#")
        device.send("exit")
        if not "eUSB partition completed." in output:
            manager.error("eUSB partition failed. Please check session.log.")
        output = device.send("show media")

        eusb_size = re.search("/harddiskb:.* ([.\d]+)G", output)

        if not eusb_size:
            manager.error("Unexpected output from CLI 'show media'.")

        if eusb_size.group(1) < "1.0":
            manager.error("/harddiskb:/ is smaller than 1 GB after running /pkg/bin/resize_eusb. " +
                          "Please make sure that the device has either RP2 or RSP4.")

    @staticmethod
    def _check_fpd(device, iosxr_run_nodes):
        """
        Check the versions of migration related FPD's on device. Return a dictionary
        that tells which FPD's on which node needs upgrade.

        :param device: the connection to the device
        :param iosxr_run_nodes: a list of strings representing all nodes(RSP/RP/LC) on device
                                that we actually will need to make sure that the FPD upgrade
                                later on completes successfully.
        :return: a dictionary with string FPD type as key, and a list of the string names of
                 nodes(RSP/RP/LC) as value.
        """
        fpdtable = device.send("show hw-module fpd location all")

        subtype_to_locations_need_upgrade = {}

        for fpdtype in FPDS_CHECK_FOR_UPGRADE:
            match_iter = re.finditer(NODE + "[-.A-Z0-9a-z\s]*?" + fpdtype + "[-.A-Z0-9a-z\s]*?(No|Yes)", fpdtable)

            for match in match_iter:
                if match.group(1) in iosxr_run_nodes:
                    if match.group(2) == "No":
                        if not fpdtype in subtype_to_locations_need_upgrade:
                            subtype_to_locations_need_upgrade[fpdtype] = []
                        subtype_to_locations_need_upgrade[fpdtype].append(match.group(1))

        return subtype_to_locations_need_upgrade

    @staticmethod
    def _ensure_updated_fpd(manager, device, packages, iosxr_run_nodes, version):
        """
        Upgrade FPD's if needed.
        Steps:
        1. Check if the FPD package is already active on device.
           Error out if not.
        2. Check if the same FPD SMU is already active on device.
           (Possibly by a previous Pre-Migrate action)
        3. Install add, activate and commit the FPD SMU if not installed.
        4. Check version of the migration related FPD's. Get the dictionary
           of FPD types mapped to locations for which we need to check for
           upgrade successs.
        5. Force install the FPD types that need upgrade on all locations.
           Check FPD related sys log to make sure all necessary upgrades
           defined by the dictionary complete successfully.

        :param manager: the plugin manager
        :param device: the connection to the device
        :param packages: all user selected packages from scheduling the Pre-Migrate
        :param iosxr_run_nodes: the list of string nodes names we get from running
                                PreMigratePlugin._get_iosxr_run_nodes
        :param version: the current software version. i.e., "5.3.3"
        :return: True if no error occurred.
        """

        manager.log("Checking if FPD package is actively installed...")
        active_packages = device.send("show install active summary")

        match = re.search("fpd", active_packages)

        if not match:
            manager.error("No FPD package is active on device. Please install the FPD package on device first.")

        manager.log("Checking if the FPD SMU has been installed...")
        pie_packages = []
        for package in packages:
            if package.find(".pie") > -1:
                pie_packages.append(package)

        if len(pie_packages) != 1:
            manager.error("Please select exactly one FPD SMU pie on server repository for FPD upgrade. " +
                          "The filename must contains '.pie'")

        name_of_fpd_smu = pie_packages[0].split(".pie")[0]

        install_summary = device.send("show install active summary")

        match = re.search(name_of_fpd_smu, install_summary)

        if not match:

            if version < RELEASE_VERSION_DOES_NOT_NEED_FPD_SMU:

                # Step 1: Install add the FPD SMU
                manager.log("FPD upgrade - install add the FPD SMU...")
                PreMigratePlugin._run_install_action_plugin(manager, device, InstallAddPlugin, "install add")

                # Step 2: Install activate the FPD SMU
                manager.log("FPD upgrade - install activate the FPD SMU...")
                PreMigratePlugin._run_install_action_plugin(manager, device, InstallActivatePlugin, "install activate")

                # Step 3: Install commit the FPD SMU
                manager.log("FPD upgrade - install commit the FPD SMU...")
                PreMigratePlugin._run_install_action_plugin(manager, device, InstallCommitPlugin, "install commit")

        else:
            manager.log("The selected FPD SMU {} is found already active on device.".format(pie_packages[0]))

        # check for the FPD version, if FPD needs upgrade,
        manager.log("Checking FPD versions...")
        subtype_to_locations_need_upgrade = PreMigratePlugin._check_fpd(device, iosxr_run_nodes)

        if subtype_to_locations_need_upgrade:

            # Force upgrade all FPD's in RP and Line card that need upgrade, with the FPD pie or both the FPD
            # pie and FPD SMU depending on release version
            PreMigratePlugin._upgrade_all_fpds(manager, device, subtype_to_locations_need_upgrade)

        return True

    @staticmethod
    def _run_install_action_plugin(manager, device, install_plugin, install_action_name):
        """Instantiate other install actions(install add, activate and commit) on same given packages"""
        try:
            install_plugin.start(manager, device)
        except PluginError as e:
            manager.error("Failed to {} the FPD SMU - ({}): {}".format(install_action_name, e.errno, e.strerror))
        except AttributeError:
            device.disconnect()
            manager.log("Disconnected...")
            raise PluginError("Failed to {} the FPD SMU. Please check session.log for details of failure.".format(
                install_action_name)
            )

    @staticmethod
    def _upgrade_all_fpds(manager, device, subtype_to_locations_need_upgrade):
        """Force upgrade certain FPD's on all locations. Check for success. """
        def send_newline(ctx):
            ctx.ctrl.sendline()
            return True

        def send_yes(ctx):
            ctx.ctrl.sendline("yes")
            return True

        def error(ctx):
            ctx.message = "Error upgrading FPD."
            return False

        def timeout(ctx):
            ctx.message = "Timeout upgrading FPD."
            return False

        for fpdtype in subtype_to_locations_need_upgrade:

            manager.log("FPD upgrade - start to upgrade FPD {} on all locations".format(fpdtype))

            CONFIRM_CONTINUE = re.compile("Continue\? \[confirm\]")
            CONFIRM_SECOND_TIME = re.compile("Continue \? \[no\]:")
            UPGRADE_END = re.compile("FPD upgrade has ended.")

            events = [device.prompt, CONFIRM_CONTINUE, CONFIRM_SECOND_TIME, UPGRADE_END, TIMEOUT]
            transitions = [
                (CONFIRM_CONTINUE, [0], 1, send_newline, TIMEOUT_FOR_FPD_UPGRADE),
                (CONFIRM_SECOND_TIME, [1], 2, send_yes, TIMEOUT_FOR_FPD_UPGRADE),
                (UPGRADE_END, [1, 2], 3, None, 120),
                (device.prompt, [3], -1, None, 0),
                (device.prompt, [1, 2], -1, error, 0),
                (TIMEOUT, [0, 1, 2], -1, timeout, 0),

            ]

            if not device.run_fsm(PreMigratePlugin.DESCRIPTION,
                                  "admin upgrade hw-module fpd {} force location all".format(fpdtype),
                                  events, transitions, timeout=30):
                manager.error("Error while upgrading FPD subtype {}. Please check session.log".format(fpdtype))

            fpd_log = device.send("show log | include fpd")

            for location in subtype_to_locations_need_upgrade[fpdtype]:

                pattern = "Successfully\s*(?:downgrade|upgrade)\s*{}.*location\s*{}".format(fpdtype, location)
                fpd_upgrade_success = re.search(pattern, fpd_log)

                if not fpd_upgrade_success:
                    manager.error("Failed to upgrade FPD subtype {} on location {}. ".format(fpdtype, location) +
                                  "Please check session.log.")
        return True

    @staticmethod
    def _create_config_logs(manager, csvfile, supported_log_name, unsupported_log_name, hostname, filename):
        """
        Create two logs for migrated configs that are unsupported and supported by eXR.
        They are stored in the same directory as session log, for user to view.

        :param manager: the plugin manager
        :param csvfile: the string csv filename generated by running NoX on original config.
        :param supported_log_name: the string filename for the supported configs log
        :param unsupported_log_name: the string filename for the unsupported configs log
        :param hostname: string hostname of device, as recorded on CSM.
        :param filename: string filename of original config
        :return: None if no error occurred
        """

        supported_config_log = os.path.join(manager.csm.log_directory, supported_log_name)
        unsupported_config_log = os.path.join(manager.csm.log_directory, unsupported_log_name)
        try:
            with open(supported_config_log, 'w') as supp_log:
                with open(unsupported_config_log, 'w') as unsupp_log:
                    supp_log.write('Configurations Known and Supported to the NoX Conversion Tool \n \n')

                    unsupp_log.write('Configurations Unprocessed by the NoX Conversion Tool (Comments, Markers,' +
                                     ' or Unknown/Unsupported Configurations) \n \n')

                    supp_log.write('{0[0]:<8} {0[1]:^20} \n'.format(("Line No.", "Configuration")))
                    unsupp_log.write('{0[0]:<8} {0[1]:^20} \n'.format(("Line No.", "Configuration")))
                    with open(csvfile, 'rb') as csvfile:
                        reader = csv.reader(csvfile)
                        for row in reader:
                            if len(row) >= 3 and row[1].strip() == "KNOWN_SUPPORTED":
                                supp_log.write('{0[0]:<8} {0[1]:<} \n'.format((row[0], row[2])))
                            elif len(row) >= 3:
                                unsupp_log.write('{0[0]:<8} {0[1]:<} \n'.format((row[0], row[2])))

                    msg = "\n \nPlease find original configuration in csm_data/migration/{}/{} \n".format(hostname,
                                                                                                          filename)
                    supp_log.write(msg)
                    unsupp_log.write(msg)
                    if filename.split('.')[0] == 'admin':
                        msg2 = "The final converted configuration is in csm_data/migration/" + \
                               hostname + "/" + CONVERTED_ADMIN_CAL_CONFIG_IN_CSM + \
                               " and csm_data/migration/" + hostname + "/" + CONVERTED_ADMIN_XR_CONFIG_IN_CSM
                    else:
                        msg2 = "The final converted configuration is in csm_data/migration/" + \
                               hostname + "/" + CONVERTED_XR_CONFIG_IN_CSM
                    supp_log.write(msg2)
                    unsupp_log.write(msg2)
                    csvfile.close()
                unsupp_log.close()
            supp_log.close()
        except:
            # PreMigratePlugin._disconnect_and_raise_error(manager, device, err_msg)
            manager.error("Error writing diagnostic files - in " + manager.csm.log_directory +
                          " during configuration migration.")

    @staticmethod
    def _filter_server_repository(manager, server):
        if not server:
            manager.error("Pre-Migrate missing server repository object.")
        if server.server_type != ServerType.FTP_SERVER and server.server_type != ServerType.TFTP_SERVER and \
           server.server_type != ServerType.SFTP_SERVER:
            manager.error("Pre-Migrate does not support " + server.server_type + " server repository.")

    @staticmethod
    def _save_config_to_csm_data(manager, device, files, admin=False):
        """
        Copy the admin configuration or IOS-XR configuration
        from device to csm_data.
        """

        try:
            cmd = "admin show run" if admin else "show run"
            output = device.send(cmd, timeout=TIMEOUT_FOR_COPY_CONFIG)
            ind = output.rfind('Building configuration...\n')

        except pexpect.TIMEOUT:
            manager.error("CLI '{}' timed out after 1 hour.".format(cmd))

        for file_path in files:
            # file = '../../csm_data/migration/<hostname>' + filename
            file_to_write = open(file_path, 'w+')
            file_to_write.write(output[(ind+1):])
            file_to_write.close()

    @staticmethod
    def _handle_configs(manager, device, hostname, server, repo_url, fileloc, nox_to_use, config_filename):
        """
        1. Copy admin and XR configs from device to tftp server repository.
        2. Copy admin and XR configs from server repository to csm_data/migration/<hostname>/
        3. Copy admin and XR configs from server repository to session log directory as
           show-running-config.txt and admin-show-running-config.txt for comparisons
           after Migrate or Post-Migrate. (Diff will be generated.)
        4. Run NoX on admin config first. This run generates 1) eXR admin/calvados config
           and POSSIBLY 2) eXR XR config.
        5. Run NoX on XR config if no custom eXR config has been selected by user when
           Pre-Migrate is scheduled. This run generates eXR XR config.
        6. Copy all converted configs to the server repository and then from there to device.
           Note if user selected custom eXR XR config, that will be uploaded instead of
           the NoX migrated original XR config.

        :param manager: the plugin manager
        :param device: the connection to the device
        :param hostname: string hostname of device, as recorded on CSM.
        :param repo_url: the URL of the selected TFTP server repository. i.e., tftp://223.255.254.245/tftpboot
        :param fileloc: the string path ../../csm_data/migration/<hostname>
        :param nox_to_use: the name of the NoX binary executable
        :param config_filename: the user selected string filename of custom eXR XR config.
                                If it's '', nothing was selected.
                                If selected, this file must be in the server repository.
        :return: None if no error occurred.
        """

        manager.log("Saving the current configurations on device into server repository and csm_data")

        PreMigratePlugin._save_config_to_csm_data(manager, device,
                                                  [os.path.join(fileloc, ADMIN_CONFIG_IN_CSM),
                                                   os.path.join(manager.csm.log_directory,
                                                                manager.file_name_from_cmd("admin show running-config"))
                                                   ], admin=True)

        PreMigratePlugin._save_config_to_csm_data(manager, device, [os.path.join(fileloc, XR_CONFIG_IN_CSM),
                                                  os.path.join(manager.csm.log_directory,
                                                               manager.file_name_from_cmd("show running-config"))],
                                                  admin=False)

        manager.log("Converting admin configuration file with configuration migration tool")
        PreMigratePlugin._run_migration_on_config(manager, device, fileloc,
                                                  ADMIN_CONFIG_IN_CSM, nox_to_use, hostname)

        # ["admin.cal"]
        config_files = [CONVERTED_ADMIN_CAL_CONFIG_IN_CSM]
        # ["admin_calvados.cfg"]
        config_names_on_device = [ADMIN_CAL_CONFIG_ON_DEVICE]
        if not config_filename:

            manager.log("Converting IOS-XR configuration file with configuration migration tool")
            PreMigratePlugin._run_migration_on_config(manager, device, fileloc,
                                                      XR_CONFIG_IN_CSM, nox_to_use, hostname)

            # "xr.iox"
            config_files.append(CONVERTED_XR_CONFIG_IN_CSM)
            # "iosxr.cfg"
            config_names_on_device.append(XR_CONFIG_ON_DEVICE)

        # admin.iox
        if os.path.isfile(os.path.join(fileloc, CONVERTED_ADMIN_XR_CONFIG_IN_CSM)):
            config_files.append(CONVERTED_ADMIN_XR_CONFIG_IN_CSM)
            config_names_on_device.append(ADMIN_XR_CONFIG_ON_DEVICE)

        manager.log("Uploading the migrated configuration files to server repository and device.")

        config_names_in_repo = [hostname + "_" + config_name for config_name in config_files]

        if PreMigratePlugin._upload_files_to_server_repository(manager,
                                                               [os.path.join(fileloc, config_name)
                                                                for config_name in config_files],
                                                               server, config_names_in_repo):

            if config_filename:
                config_names_in_repo.append(config_filename)
                # iosxr.cfg
                config_names_on_device.append(XR_CONFIG_ON_DEVICE)

            PreMigratePlugin._copy_files_to_device(manager, device, server, repo_url, config_names_in_repo,
                                                   [ISO_LOCATION + config_name
                                                    for config_name in config_names_on_device],
                                                   timeout=TIMEOUT_FOR_COPY_CONFIG)

    @staticmethod
    def _copy_iso_to_device(manager, device, server, packages, repo_url):
        """Copy the user selected ASR9K eXR image from server repository to /harddiskb:/ on device."""
        found_iso = False
        iso_image_pattern = re.compile("asr9k.*\.iso.*")
        for package in packages:
            if iso_image_pattern.match(package):
                PreMigratePlugin._copy_files_to_device(manager, device, server, repo_url, [package],
                                                       [ISO_LOCATION + package], timeout=TIMEOUT_FOR_COPY_ISO)
                found_iso = True
                break
        if not found_iso:
            manager.error("No ASR9K IOS XR 64 Bit image found in packages.")

    @staticmethod
    def _find_nox_to_use():
        """
        Find out if the linux system is 32 bit or 64 bit. NoX currently only has a binary executable
        compiled for 64 bit.
        """
        check_32_or_64_system = subprocess.Popen(['uname', '-a'], stdout=subprocess.PIPE)

        out, err = check_32_or_64_system.communicate()

        if err:
            raise PluginError("Failed to execute 'uname -a' on the linux system.")

        if "x86_64" in out:
            return NOX_64_BINARY
        else:
            raise PluginError("The configuration migration tool NoX is not available for 32 bit linux system.")

    @staticmethod
    def start(manager, device, *args, **kwargs):

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

        db_session = DBSession()
        server = db_session.query(Server).filter(Server.id == manager.csm.install_job.server_id).first()

        PreMigratePlugin._filter_server_repository(manager, server)

        db_session.close()

        hostname_for_filename = re.sub("[()\s]", "_", manager.csm.host.hostname)
        hostname_for_filename = re.sub("_+", "_", hostname_for_filename)

        fileloc = manager.csm.migration_directory + hostname_for_filename

        if not os.path.exists(fileloc):
            os.makedirs(fileloc)

        manager.log("Checking if some migration requirements are met.")

        if device.os_type != "XR":
            manager.error('Device is not running ASR9K Classic XR. Migration action aborted.')

        version = re.search("(\d\.\d\.\d).*", device.os_version)

        if not version:
            manager.error("Bad os_version.")

        if version < MINIMUM_RELEASE_VERSION_FOR_MIGRATION:
            manager.error("The minimal release version required for migration is 5.3.3. " +
                          "Please upgrade to at lease R5.3.3 before scheduling migration.")

        PreMigratePlugin._ping_repository_check(manager, device, server_repo_url)

        try:
            NodeStatusPlugin.start(manager, device)
        except PluginError:
            manager.error("Not all nodes are in valid states. Pre-Migrate aborted. " +
                          "Please check session.log to trouble-shoot.")

        iosxr_run_nodes = PreMigratePlugin._get_iosxr_run_nodes(manager, device)

        manager.log("Resizing eUSB partition.")
        PreMigratePlugin._resize_eusb(manager, device)

        nox_to_use = manager.csm.migration_directory + PreMigratePlugin._find_nox_to_use()

        # nox_to_use = manager.csm.migration_directory + NOX_FOR_MAC

        if not os.path.isfile(nox_to_use):
            manager.error("The configuration conversion tool {} is missing. ".format(nox_to_use) +
                          "CSM should have downloaded it from CCO when migration actions were scheduled.")

        PreMigratePlugin._handle_configs(manager, device, hostname_for_filename, server,
                                         server_repo_url, fileloc, nox_to_use, config_filename)

        manager.log("Copying the eXR ISO image from server repository to device.")
        PreMigratePlugin._copy_iso_to_device(manager, device, server, packages, server_repo_url)

        PreMigratePlugin._ensure_updated_fpd(manager, device, packages, iosxr_run_nodes, version)

        return True
