# =============================================================================
#
# Copyright (c)  2015, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
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
import itertools
import time
import os

import package_lib
import pexpect
import condoor
from condoor import TIMEOUT
import shutil
from database import DBSession
from models import Server

TIMEOUT_FOR_COPY_CONFIG = 3600


def watch_operation(manager, device, op_id=0):
        """
        Function to keep watch on progress of operation
        and report KB downloaded.

        """
        pat_no_install = r"There are no install requests in operation"
        failed_oper = r"Install operation (\d+) failed"
        op_progress = r"The operation is (\d+)% complete"
        op_download = r"(.*)KB downloaded: Download in progress"

        cmd_show_install_request = "admin show install request"

        manager.log("Watching the operation {} to complete".format(op_id))
        last_status = None

        propeller = itertools.cycle(["|", "/", "-", "\\", "|", "/", "-", "\\"])

        success = "Install operation {} completed successfully".format(op_id)

        finish = False
        while not finish:
            try:
                # this is to catch the successful operation as soon as possible
                device.send("", wait_for_string=success, timeout=20)
                finish = True
            except condoor.CommandTimeoutError:
                pass

            message = ""
            output = device.send(cmd_show_install_request)
            if op_id in output:
                # FIXME reconsider the logic here
                result = re.search(op_progress, output)
                if result:
                    status = result.group(0)
                    message = "{} {}".format(propeller.next(), status)

                result = re.search(op_download, output)
                if result:
                    status = result.group(0)
                    message += "\r\n<br>{}".format(status)

                if message != last_status:
                    manager.csm.post_status(message)
                    last_status = message

            if pat_no_install in output:
                break

        return output


def get_package(device, manager):
    if device.os_type == "XR":
        if hasattr(manager.csm, 'active_cli'):
            output = device.send("admin show install active summary")
            manager.csm.active_cli = output
        if hasattr(manager.csm, 'inactive_cli'):
            output = device.send("admin show install inactive summary")
            manager.csm.inactive_cli = output
        if hasattr(manager.csm, 'committed_cli'):
            output = device.send("admin show install committed summary")
            manager.csm.committed_cli = output

    if device.os_type == "eXR":
        device.send("admin")
        if hasattr(manager.csm, 'active_cli'):
            output = device.send("show install active")
            manager.csm.active_cli = output
        if hasattr(manager.csm, 'inactive_cli'):
            output = device.send("show install inactive")
            manager.csm.inactive_cli = output
        if hasattr(manager.csm, 'committed_cli'):
            output = device.send("show install committed")
            manager.csm.committed_cli = output
        device.send("exit")

def wait_for_reload(manager, device):
    """
     Wait for system to come up with max timeout as 25 Minutes

    """
    device.disconnect()
    time.sleep(60)

    device.reconnect(max_timeout=1500)  # 25 * 60 = 1500
    timeout = 3600
    poll_time = 30
    time_waited = 0
    xr_run = "IOS XR RUN"

    cmd = "admin show platform"
    manager.log("Waiting for all nodes to come up")
    time.sleep(100)
    while 1:
        # Wait till all nodes are in XR run state
        time_waited += poll_time
        if time_waited >= timeout:
            break
        time.sleep(poll_time)
        output = device.send(cmd)
        if xr_run in output:
            inventory = package_lib.parse_xr_show_platform(output)
            if package_lib.validate_xr_node_state(inventory, device):
                manager.log("All nodes in desired state")
                return True

    # Some nodes did not come to run state
    manager.error("Not all nodes have came up: {}".format(output))
    # this will never be executed
    return False


def watch_install(manager, device, oper_id, install_cmd):
    # FIXME: Add description

    """

    """
    success_oper = r'Install operation (\d+) completed successfully'
    completed_with_failure = 'Install operation (\d+) completed with failure'
    failed_oper = r'Install operation (\d+) failed'
    failed_incr= r'incremental.*parallel'
    # restart = r'Parallel Process Restart'
    install_method = r'Install [M|m]ethod: (.*)'
    op_success = "The install operation will continue asynchronously"

    watch_operation(manager, device, oper_id)

    output = device.send("admin show install log {} detail".format(oper_id))
    if re.search(failed_oper, output):
        if re.search(failed_incr, output):
            manager.log("Retrying with parallel reload option")
            cmd = install_cmd + " parallel-reload"
            output = device.send(cmd)
            if op_success in output:
                result = re.search('Install operation (\d+) \'', output)
                if result:
                    op_id = result.group(1)
                    watch_operation(manager, device, op_id)
                    output = device.send("admin show install log {} detail".format(oper_id))
                else:
                    manager.log_install_errors(output)
                    manager.error("Operation ID not found")
        else:
            manager.log_install_errors(output)
            manager.error(output)

    result = re.search(install_method, output)
    if result:
        restart_type = result.group(1).strip()
        manager.log("{} Pending".format(restart_type))
        if restart_type == "Parallel Reload":
            if re.search(completed_with_failure, output):
                manager.log("Install completed with failure, going for reload")
            elif re.search(success_oper, output):
                manager.log("Install completed successfully, going for reload")
            return wait_for_reload(manager, device)
        elif restart_type == "Parallel Process Restart":
            return True

    manager.log_install_errors(output)
    return False


def install_activate_deactivate(manager, device, cmd):
    op_success = "The install operation will continue asynchronously"
    manager.log("Waiting the operation to continue asynchronously")
    output = device.send(cmd, timeout=7200)
    result = re.search('Install operation (\d+) \'', output)
    if result:
        op_id = result.group(1)
    else:
        manager.log_install_errors(output)
        manager.error("Operation failed")

    if op_success in output:
        success = watch_install(manager, device, op_id, cmd)
        if not success:
            manager.error("Reload or boot failure")
        get_package(device, manager)
        manager.log("Operation {} finished successfully".format(op_id))
        return
    else:
        manager.log_install_errors(output)
        manager.error("Operation {} failed".format(op_id))


def install_add_remove(manager, device, cmd, has_tar=False):
    manager.log("Waiting the operation to continue asynchronously")
    output = device.send(cmd, timeout=7200)
    result = re.search('Install operation (\d+) \'', output)
    if result:
        op_id = result.group(1)
        # this needs to be clarified
        if hasattr(manager.csm, 'operation_id'):
            if has_tar is True:
                manager.csm.operation_id = op_id
                manager.log("The operation {} stored".format(op_id))
    else:
        manager.log_install_errors(output)
        manager.error("Operation failed")
        return  # for sake of clarity

    op_success = "The install operation will continue asynchronously"
    failed_oper = r'Install operation {} failed'.format(op_id)
    if op_success in output:
        watch_operation(manager, device, op_id)
        output = device.send("admin show install log {} detail".format(op_id))
        if re.search(failed_oper, output):
            manager.log_install_errors(output)
            manager.error("Operation {} failed".format(op_id))
            return  # for same of clarity

        get_package(device, manager)
        manager.log("Operation {} finished successfully".format(op_id))
        return  # for sake of clarity
    else:
        manager.log_install_errors(output)
        manager.error("Operation {} failed".format(op_id))


def clear_cfg_inconsistency(manager, device):
    """
    perform clear configuration inconsistency both from exec and
    admin-exec mode
    """

    manager.log("Checking config consistency")

    cmd = 'clear configuration inconsistency'
    adm_cmd = 'admin clear configuration inconsistency'

    # FIXME:  This is not good enough. Better OK checking needed
    output = device.send(cmd)
    if '...OK' not in output:
        manager.error("{} command execution failed".format(cmd))

    output = device.send(adm_cmd)
    if '...OK' not in output:
        manager.error("{} command execution failed".format(cmd))


def copy_running_config_to_repo(manager, device, repository, filename, admin=""):
    """
    Copy the admin configuration or IOS-XR configuration
    from device to user's selected server repository.
    """

    def send_newline(ctx):
        ctx.ctrl.sendline()
        return True

    def error(ctx):
        ctx.message = "nvgen error"
        return False

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
    if not device.run_fsm("copy running-config to tftp", command, events, transitions, timeout=20):
        manager.error("Failed to copy running-config to your repository. \
                      Please check session.log for error and fix the issue.")
        return False


def save_config_to_csm_data(manager, device, files, admin=False):
    """
    Copy the admin configuration or IOS-XR configuration
    from device to csm_data.
    """

    try:
        cmd="admin show run" if admin else "show run"
        output = device.send(cmd, timeout=TIMEOUT_FOR_COPY_CONFIG)
        ind = output.rfind('Building configuration...\n')

    except pexpect.TIMEOUT:
        manager.error("CLI '{}' timed out after 1 hour.".format(cmd))

    for file_path in files:
        # file = '../../csm_data/migration/<hostname>' + filename
        file_to_write = open(file_path, 'w+')
        file_to_write.write(output[(ind+1):])
        file_to_write.close()


def copy_files_from_tftp_to_csm_data(manager, device, repo_url, source_filenames, dest_files):
    """Copy files from the server repository"""
    db_session = DBSession()
    server = db_session.query(Server).filter(Server.server_url == repo_url).first()
    if not server:
        manager.error("Cannot map the tftp server url to the tftp server repository. \
                      Please check the tftp repository setup on CSM.")

    for x in range(0, len(source_filenames)):
        try:
            shutil.copy(server.server_directory + os.sep + source_filenames[x], dest_files[x])
        except:
            db_session.close()
            device.disconnect()
            manager.error("Exception was thrown while copying file {}/{} to {}.".format(server.server_directory,
                                                                                        source_filenames[x],
                                                                                        dest_files[x]))

    db_session.close()


def get_all_nodes(device):
    """Get the list of string node names(all available RSP/RP/LC)"""
    device.send("admin")
    output = device.send("show platform")
    nodes = re.findall("(\d+/(?:RS?P)?\d+)", output)
    device.send("exit")
    return nodes


def wait_for_final_band(device):
    """This is for ASR9K eXR. Wait for all present nodes to come to FINAL Band."""
    nodes = get_all_nodes(device)
     # Wait for all nodes to Final Band
    timeout = 1080
    poll_time = 20
    time_waited = 0

    cmd = "show platform vm"
    while 1:
        # Wait till all nodes are in FINAL Band
        time_waited += poll_time
        if time_waited >= timeout:
            break
        time.sleep(poll_time)
        output = device.send(cmd)
        all_nodes_present = True
        for node in nodes:
            if not node in output:
                all_nodes_present = False
                break
        if all_nodes_present and check_sw_status(output):
            return True

    # Some nodes did not come to FINAL Band
    return False


def check_sw_status(output):
    """Check is a node has FINAL Band status"""
    lines = output.splitlines()

    for line in lines:
        line = line.strip()
        if len(line) > 0 and line[0].isdigit():
            sw_status = line[48:64].strip()
            if "FINAL Band" not in sw_status:
                return False
    return True


