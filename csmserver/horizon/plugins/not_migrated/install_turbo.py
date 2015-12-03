# =============================================================================
# install_turbo.py - plugin for install IOS-XR images by turbo boot
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

from au.plugins.plugin import IPlugin
from time import sleep
import re


# wainting long time (5 minutes)
LONG_WAIT = 300


class InstallTurboPlugin(IPlugin):

    """
    A plugin for turbo boot
    This plugin accesses rommon and set rommon variables.
    A router is reloaded a few times.
    Console access is needed.
    This plugin does not work on telnet connection.
    Arguments:
    T.B.D.
    """
    NAME = "INSTALL_TURBOBOOT"
    DESCRIPTION = "Turbo Boot Installation"
    TYPE = "UPGRADE"
    VERSION = "0.0.1"

    def get_vm_image(self, pkg_list):
        vm_image = None

        with open(pkg_list, 'r') as f:
            count = 0
            for line in f:
                match = re.match(r'.+\.vm-.+$|.+\.vm$', line)
                if match:
                    count += 1
                    vm_image = match.group()

            if count == 0:
                self.error(
                    "pkg-file-list does not include a vm image name for turbo boot")
            elif count > 1:
                self.error(
                    "pkg-file-list include more than one vm image name for turbo boot")

            return vm_image

    # get the standby rp into rommon mode from the active console
    #
    # This utility does not have Standby RP console access.
    # We can shutdown Standby RP from Active RP console but we cannot restart Standby RP.
    # An operator has to restart Standby RP manually after all processes done
    def shutdown_standby_rp(self, device):
        srp = None
        # get Standby RP
        success, output = device.execute_command('admin show platform')
        if success:
            print output
            lines = output.split("\n")
            for line in lines:
                if line.find('Standby') >= 0:
                    match = re.search('\d+/(RSP|RP)\d+/CPU\d+', line)
                    srp = match.group()
                    run_state = 'IOS XR RUN' in line

        # No Standby RP, nothing to do
        if not srp:
            return True

        # Standby RP is in IOS XR RUN state
        if run_state:
            cmd = 'admin config-register 0x0 location {}'.format(srp)
            success, output = device.execute_command(cmd)
            print cmd
            if not success:
                self.error(
                    "Failed to set rommon var\n{}\n{}".format(cmd, output))

            # reload Standby RP
            cmd = 'admin reload location {} \r \r'.format(srp)
            status, output = device.execute_command(cmd)
            if not status:
                self.error("Reload failed \n{}\n{}".format(cmd, output))

            print """
                Standby RP %s has been shut down for Turboboot.
                This script cannot restart Standby RP automatically.
                Please restart Standby RP as follows after all processes done.
                rommon 1> unset BOOT
                rommon 2> confreg 0x102
                rommon 3> sync
                rommon 4> reset""" % (srp)

        else:
            self.error("""
                Stabdby RP is not in IOS XR RUN state. Turbo boot can not be
                performed""")

        return True

    # set 0x0 to confreg and reload the device
    def reload(self, device):

        cmd = 'admin config-register 0x0 \r \r \r'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success
        cmd = 'reload \r \r \r \r'
        success, output = device.execute_command(cmd)
        print output, "<-----------------", success
        if not success:
            self.error("Failed to reload to get RP on rommon")
        print "!" * 80

    # execute turbo boot
    def turbo_boot(self, device, repository, vm_image):
        return
        retval = 0
        prompt = 'rommon \w+ >'
        boot_cmd = "boot " + repository + vm_image

        device.sendline('set')
        try:
            status = device.expect(
                ['IP_ADDRESS=(\d+\.\d+\.\d+\.\d+)'], timeout=10)
        except:
            aulog.error("IP_ADDRESS is not set. "
                        "Turbo boot needs IP_ADDRESS set at rommon")
        device.expect(prompt)
        device.sendline('unset BOOT')
        device.expect(prompt)
        device.sendline('TURBOBOOT=on,disk0')
        device.expect(prompt)
        device.sendline('sync')
        device.expect(prompt)
        device.sendline('set')
        device.expect(prompt)
        sleep(10)
        device.sendline(boot_cmd)

        # waiting for the start of file download
        status = device.expect(['![!\.][!\.][!\.][!\.]', prompt], timeout=180)
        if status == 1:
            # retry once more
            device.sendline(boot_cmd)
            device.expect('![!\.][!\.][!\.][!\.]', timeout=180)

        return True

    # count the number of cards in valid state
    def count_valid_cards(self, device):
        valid_state = 'IOS XR RUN|PRESENT|READY|UNPOWERED|FAILED|OK|DISABLED'
        retval = 0
        valid_card_num = 0
        cmd = "admin show platform"
        status = 1
        card_num = 0
        try:
            device.sendline(cmd)
            # status = 1 means to hit the line of RP or LC
            while status == 1:
                status = device.expect([self.prompt, '\d+/\w+/\w+ .+\r'])
                if status == 1:
                    card_num += 1
                    if re.search(valid_state, device.after):
                        valid_card_num += 1
        except Exception as e:
            aulog.debug(cmd)
            aulog.debug(device.before + str(e))
            retval = -1
        return retval, card_num, valid_card_num

    # watch all cards status by show platform command
    def watch_platform(self, device, pre_valid_card_num):
        try:
            # this loop will be existed when all cards are in valid states
            counter = 0
            while counter < 60:
                retval, card_num, valid_card_num = self.count_valid_cards(
                    device)
                if retval == -1:
                    return retval
                elif valid_card_num >= pre_valid_card_num:
                    break
                sleep(60)  # wait for one minutes
                counter += 1

            if valid_card_num >= pre_valid_card_num:
                retval = 0
                aulog.info("All cards seem to reach the valid status")
            else:
                retval = -1
                aulog.error("The number of cards in valid state is less "
                            "than the number before turboboot. "
                            "Something worrying happens on cards "
                            "still in invalid state. The number "
                            "of original valid cards was %s. "
                            "The number of current valid cards is %s."
                            % (str(pre_valid_card_num), str(valid_card_num)))
        except Exception as e:
            aulog.debug("In watch_platform : %s " % (str(e)))
            retval = -1

        return retval

    # watch the progress of turbo boot
    def _watch_operation(self, device):
        """
         Wait for system to come up with max timeout as 10 Minutes

        """
        return
        timeout = 600
        poll_time = 30
        time_waitetd = 0
        xr_run = "IOS XR RUN"

        success = False
        print "System going for reload., please wait!!"
        connected = False
        time.sleep(180)

        while 1:
            time_waitetd += poll_time
            if time_waitetd >= timeout:
                break
            time.sleep(poll_time)

            if connected:
                cmd = "admin show install active summary"
                success, output = device.execute_command(cmd)
                if success and 'mem:' in output:
                    #inventory = pkgutils.parse_xr_show_platform(output)
                    # if pkgutils.validate_xr_node_state(inventory, device):
                    #    return True
                    print output
                    return True
            else:
                print "Trying to connect ...."
                try:
                    success = device.reconnect()
                except:
                    print("Device Error: {}".format(device.error_code))

                if success:
                    connected = True
        return False


#    def _watch_operation(self, device)
#
#        try:
#            while 1:
#                status = device.expect(['Press RETURN to get started', timeout], timeout=LONG_WAIT)
#                if status == 1:
#                    if len(device.before) > 0:
#                        continue
#                    else:
#                        retval = -1
#                        return retval
#                else:
#                    break
#
#            while 1:
#                status = device.expect(['Turboboot completed successfully', timeout], timeout=LONG_WAIT)
#                if status == 1:
#                    if len(device.before) > 0:
#                        continue
#                    else:
#                        retval = -1
#                        return retval
#                else:
#                    aulog.info("Turboboot completed successfully")
#                    break
#
#            while 1:
#                status = device.expect(['Press RETURN to get started', timeout], timeout=LONG_WAIT)
#                if status == 1:
#                    if len(device.before) > 0:
#                        continue
#                    else:
#                        retval = -1
#                        return retval
#                else:
#                    aulog.info("2nd boot is in progress")
#                    aulog.debug("device.before")
#                    break
#
# login console
#            retry_count = 20
#            while retry_count:
#                try:
#                    device.send('\r')
#                    sleep(1)
#                    device.expect(USERNAME, timeout=3)
#                    device.sendline(login)
#                    device.expect(PASS, timeout=3)
#                    device.sendline(passwd)
#                    status = -1
# status = device.expect([self.prompt, ':ios#'], timeout=3)
#                    break
#                except:
#                    aulog.info(device.before)
#                    device.expect(".*")
#                    retry_count -= 1
#
#            if status == -1:
#                aulog.info("Cannot login after turboboot")
#                aulog.debug(device.before)
#                retval = -1
#                return retval
#
#            elif status == 0:
#                aulog.info("Login after turboboot successful..")
#
#            else:
#                aulog.info("Login after turboboot successful..")
#                aulog.info("But CLI prompt does not chage to " + self.prompt + ", yet.")
#
#                # wait for prompt chaging to location:devicename#
#                retry_count = 30
#                while retry_count:
#                    device.send('\r')
#                    status = device.expect([self.prompt, pexpect.TIMEOUT], timeout=60)
#                    if status == 0:
#                        aulog.info("CLI prompt has chaged to " + self.prompt)
#                        break
#                    else:
#                        aulog.info(device.before[-100:])
#                        retry_count -= 1
#
#                if retry_count == 0:
#                    aulog.info("CLI prompt does not become " + self.prompt)
#                    aulog.info("active RP does not avaliable, yet.")
#                    retval = -1
#                    return retval
#
# watch all cards status
#            retval = self.watch_platform(device, pre_valid_card_num)
#
#        except Exception as e:
#            aulog.debug("During watch operation :%s %s" % (device.before, str(e)))
#            retval = -1
#
#        return retval

    def start(self, device, *args, **kwargs):
        # check if Turboboot is requested
        if not kwargs.get('turbo_boot'):
            print "Skipped TURBOBOOT"
            return

        prompt = device.info.get('prompt')

        # Fetch the image vm name from the package list
        pkg_list = kwargs.get("pkg_file", None)
        vm_image = self.get_vm_image(pkg_list)

        # count the number of cards
        #card_num, valid_card_num = self.count_valid_cards(device)

        # get the standby rp in rommon
        self.shutdown_standby_rp(device)

        # wait for standby becomes rommon mode
        # it may take more than 10 seconds
        sleep(60)

        # reload the device and get it into rommon mode
        self.reload(device)

        self.log("Reload the router and get into ROMMON mode.")

        # execute turbo boot
        repository = kwargs.get('repository', None)

        self.log("Starting Turboboot.")
        self.turbo_boot(device, repository, vm_image)

        # monitor the progress of turbo boot
        self._watch_operation(device, login, passwd, valid_card_num)

        return True
