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

import package_lib
import condoor


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
        ctx = device.get_property("ctx")
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
                    ctx.post_status(message)
                    last_status = message

            if pat_no_install in output:
                break

        return output


def get_package(device):
    csm_ctx = device.get_property('ctx')
    if csm_ctx:
        if device.os_type == "XR":
            if hasattr(csm_ctx, 'active_cli'):
                output = device.send("admin show install active summary")
                csm_ctx.active_cli = output
            if hasattr(csm_ctx, 'inactive_cli'):
                output = device.send("admin show install inactive summary")
                csm_ctx.inactive_cli = output
            if hasattr(csm_ctx, 'committed_cli'):
                output = device.send("admin show install committed summary")
                csm_ctx.committed_cli = output

        if device.os_type == "eXR":
            if hasattr(csm_ctx, 'active_cli'):
                output = device.send("admin show install active")
                csm_ctx.active_cli = output
            if hasattr(csm_ctx, 'inactive_cli'):
                output = device.send("admin show install inactive")
                csm_ctx.inactive_cli = output
            if hasattr(csm_ctx, 'committed_cli'):
                output = device.send("admin show install committed")
                csm_ctx.committed_cli = output


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
        get_package(device)
        manager.log("Operation {} finished successfully".format(op_id))
        return
    else:
        manager.log_install_errors(output)
        manager.error("Operation {} failed".format(op_id))


def install_add_remove(manager, device, cmd, has_tar=False):
    ctx = device.get_property("ctx")
    manager.log("Waiting the operation to continue asynchronously")
    output = device.send(cmd, timeout=7200)
    result = re.search('Install operation (\d+) \'', output)
    if result:
        op_id = result.group(1)
        # this needs to be clarified
        if hasattr(ctx, 'operation_id'):
            if has_tar is True:
                ctx.operation_id = op_id
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

        get_package(device)
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


def save_data(device, key, data):
    """
    Stores (data, timestamp) tuple for key adding timestamp
    """
    ctx = device.get_property("ctx")
    if ctx:
        ctx.save_data(key, [data, time.time()])
    else:
        raise AttributeError("No CSM context in device")


def load_data(device, key):
    """
    Loads (data, timestamp) tuple for the key
    """
    ctx = device.get_property("ctx")
    if ctx:
        return ctx.load_data(key)
    else:
        raise AttributeError("No CSM context in device")
