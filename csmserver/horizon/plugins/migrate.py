# =============================================================================
# migrate.py - plugin for migrating classic XR to eXR/fleXR
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
from horizon.plugin import PluginError, Plugin
from horizon.package_lib import parse_exr_show_sdr, validate_exr_node_state
from horizon.plugin_lib import wait_for_reload, get_package

from condoor.controllers.protocols.base import PASSWORD_PROMPT, USERNAME_PROMPT, PERMISSION_DENIED, AUTH_FAILED, RESET_BY_PEER, SET_USERNAME, SET_PASSWORD, PASSWORD_OK, PRESS_RETURN,UNABLE_TO_CONNECT
from condoor.controllers.protocols.telnet import ESCAPE_CHAR, CONNECTION_REFUSED
from condoor.exceptions import ConnectionError, ConnectionAuthenticationError
from pexpect import TIMEOUT, EOF

from common import get_host
from database import DBSession

XR_PROMPT = re.compile('(\w+/\w+/\w+/\w+:.*?)(\([^()]*\))?#')


SCRIPT_BACKUP_CONFIG = "harddiskb:/classic.cfg"
SCRIPT_BACKUP_ADMIN_CONFIG = "harddiskb:/admin.cfg"

MIGRATION_TIME_OUT = 3600
NODES_COME_UP_TIME_OUT = 3600

class MigratePlugin(Plugin):

    """
    A plugin for migrating from XR to eXR/fleXR
    This plugin accesses rommon and set rommon variable EMT.
    A router is reloaded twice.
    Console access is needed.
    Arguments:
    T.B.D.
    """
    NAME = "MIGRATE"
    DESCRIPTION = "MIGRATE FROM XR TO EXR"
    TYPE = "MIGRATE"
    VERSION = "0.0.1"

    """
    @staticmethod
    def _copy_file_to_device(manager, device, repository, filename, dest):
        timeout = 1500
        success, output = device.execute_command('dir ' + dest + '/' + filename)
        cmd = 'copy ' + repository + '/' + filename + ' ' + dest
        device.execute_command(cmd, timeout=timeout, wait_for_string='?')

        if "No such file" not in output:
            device.execute_command('\r', timeout=timeout, wait_for_string='?')

        success, output = device.execute_command('\r', timeout=timeout)

        if re.search('copied\s+in', output):
            self._second_attempt_execution(device, cmd, timeout, 'copied\s+in', "failed to copy file to your repository.")
    """

    @staticmethod
    def _run_migration_script(manager, device):

        output = device.send("show platform")
        nodes = re.findall("(\d+/RS?P\d/CPU\d)", output)

        device.send("run", wait_for_string="#")

        output = device.send("ksh /pkg/bin/migrate_to_eXR -b eUSB -e 5", wait_for_string="#")

        device.send("exit")

        MigratePlugin._check_migration_script_output(manager, device, output)


        return True

    @staticmethod
    def _check_migration_script_output(manager, device, output):
        """
        check that the migration script ran without errors, and also, the configs are backed up.
        """
        lines = output.splitlines()
        for line in lines:
            if "No such file" in line:
                manager.error("Found file missing when running migration script. Please check session.log.")
            if "Error:" in line:
                manager.error("Error when running migration script. Please check session.log.")
            if "Failed to correctly write emt_mode" in line:
                manager.error("Failed to write boot mode. Please check session.log")

        output = device.send('dir {}'.format(SCRIPT_BACKUP_CONFIG))
        if "No such file" in output:
            manager.error("Migration script failed to back up the running config. Please check session.log.")
        else:
            manager.log("The running-config is backed up in {}".format(SCRIPT_BACKUP_CONFIG))

        output = device.send('dir {}'.format(SCRIPT_BACKUP_ADMIN_CONFIG))
        if "No such file" in output:
            manager.error("Migration script failed to back up the admin running config. Please check session.log.")
        else:
            manager.log("The admin running-config is backed up in {}".format(SCRIPT_BACKUP_CONFIG))

    @staticmethod
    def _configure_authentication(manager, device):

        hostname = manager.csm.host.hostname

        db_session = DBSession()

        host = get_host(db_session, hostname)
        if host is None:
            manager.error("Cannot find the current host {} in the database.".format(hostname))

        connection_param = host.connection_param[0]

        def send_return(ctx):
            ctx.ctrl.send("\r\n")
            return True

        def send_username(ctx):
            ctx.ctrl.sendline(connection_param.username)
            return True

        def send_password(ctx):
            ctx.ctrl.sendline(connection_param.password)
            return True


        events = [ESCAPE_CHAR, PASSWORD_OK, SET_USERNAME, SET_PASSWORD, USERNAME_PROMPT, PASSWORD_PROMPT,
                 XR_PROMPT, PRESS_RETURN, UNABLE_TO_CONNECT,
                 CONNECTION_REFUSED, RESET_BY_PEER, PERMISSION_DENIED,
                 AUTH_FAILED, TIMEOUT, EOF]

        transitions = [
            (ESCAPE_CHAR, [0, 1], 1, None, 20),
            (PASSWORD_OK, [0, 1], 1, send_return, 10),
            (PASSWORD_OK, [6], 6, send_return, 10),
            (PRESS_RETURN, [0, 1], 1, send_return, 10),
            (PRESS_RETURN, [6], 6, send_return, 10),
            (SET_USERNAME, [0, 1, 2, 3], 4, send_username, 20),
            (SET_USERNAME, [4], 4, None, 1),
            (SET_PASSWORD, [4], 5, send_password, 10),
            (SET_PASSWORD, [5], 6, send_password, 10),
            (USERNAME_PROMPT, [0, 1, 6, 7], 8, send_username, 10),
            (USERNAME_PROMPT, [8], 8, None, 10),
            (PASSWORD_PROMPT, [8], 9, send_password, 30),
            (XR_PROMPT, [9, 10], -1, None, 10),


            (UNABLE_TO_CONNECT, [0, 1], 11, ConnectionError("Unable to connect", device.hostname), 10),
            (CONNECTION_REFUSED, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 11, ConnectionError("Connection refused", device.hostname), 1),
            (RESET_BY_PEER, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 11, ConnectionError("Connection reset by peer", device.hostname), 1),
            (PERMISSION_DENIED, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 11, ConnectionAuthenticationError("Permission denied", device.hostname), 1),
            (AUTH_FAILED, [6, 9], 11, ConnectionAuthenticationError("Authentication failed", device.hostname), 1),
            (TIMEOUT, [0], 1, None, 20),
            (TIMEOUT, [1], 2, None, 40),
            (TIMEOUT, [2], 3, None, 60),
            (TIMEOUT, [3, 7], 11, ConnectionError("Timeout waiting to connect", device.hostname), 10),
            (TIMEOUT, [6], 7, None, 20),
            (TIMEOUT, [9], 10, None, 60),
        ]

        if not device.run_fsm(MigratePlugin.DESCRIPTION, "", events, transitions, timeout=30):
            manager.error("Failed to connect to device after reload.")


    @staticmethod
    def _reload_all(manager, device):

        device.reload(reload_timeout=MIGRATION_TIME_OUT)

        return MigratePlugin._wait_for_reload(manager, device)
        #return wait_for_reload(manager, device)


    @staticmethod
    def _wait_for_final_band(device):
         # Wait for all nodes to Final Band
        timeout = 600
        poll_time = 20
        time_waited = 0
        xr_run = "IOS XR RUN"

        cmd = "show platform vm"
        while 1:
            # Wait till all nodes are in FINAL Band
            time_waited += poll_time
            if time_waited >= timeout:
                break
            time.sleep(poll_time)
            output = device.send(cmd)
            if MigratePlugin._check_sw_status(output):
                return True

        # Some nodes did not come to FINAL Band
        return False

    @staticmethod
    def _check_sw_status(output):
        lines = output.splitlines()

        for line in lines:
            line = line.strip()
            if len(line) > 0 and line[0].isdigit():
                sw_status = line[48:63].strip()
                if sw_status != "FINAL Band":
                    return False
        return True



    @staticmethod
    def _wait_for_reload(manager, device):
        """
         Wait for system to come up with max timeout as 1 hour + 1 hour

        """
        MigratePlugin._configure_authentication(manager, device)

        #device.disconnect()
        #time.sleep(60)

        #device.reconnect(max_timeout=MIGRATION_TIME_OUT)  # 60 * 60 = 3600
        timeout = NODES_COME_UP_TIME_OUT
        poll_time = 30
        time_waited = 0
        xr_run = "IOS XR RUN"

        cmd = "show sdr"
        manager.log("Waiting for all nodes to come up")
        while 1:
            # Wait till all nodes are in XR run state
            time_waited += poll_time
            if time_waited >= timeout:
                break
            time.sleep(poll_time)
            output = device.send(cmd)
            if xr_run in output:
                inventory = parse_exr_show_sdr(output)
                if validate_exr_node_state(inventory, device):
                    return True

        # Some nodes did not come to run state
        manager.error("Not all nodes have came up: {}".format(output))
        # this will never be executed
        return False



    @staticmethod
    def start(manager, device, *args, **kwargs):

        manager.log("Run migration script to set boot mode and image path in device")
        MigratePlugin._run_migration_script(manager, device)

        # checked: reload router, now we have flexr-capable fpd

        manager.log("Reload device to boot eXR")
        MigratePlugin._reload_all(manager, device)

        manager.log("Waiting for all nodes to come to FINAL Band.")
        if MigratePlugin._wait_for_final_band(device):
            manager.log("All nodes are in FINAL Band.")
        else:
            manager.error("Not all nodes went to FINAL Band.")

        device._os_type = "eXR"

        get_package(device, manager)

        return True

