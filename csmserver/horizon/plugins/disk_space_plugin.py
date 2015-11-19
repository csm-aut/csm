#==============================================================================
# disk_space_plugin.py - Plugin for checking available disk space.
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
import re

from plugin import IPlugin

from pexpect import TIMEOUT


class DiskSpacePlugin(IPlugin):

    """
    Pre-upgrade check
    This plugin checks the available disk space
    """
    NAME = "DISK_SPACE"
    DESCRIPTION = "Disk Space Check"
    TYPE = "PRE_UPGRADE"
    VERSION = "1.0.0"
    FAMILY = ["ASR9K"]

    @staticmethod
    def _get_pie_size(manager, device, package_url):
        cmd = "admin show install pie-info " + package_url

        output = device.send(cmd)
        if output:
            for line in output.split('\n'):
                if "Compressed" in line:
                    size = long(line.split(":")[1].strip())
                    return size
                if line and line[:6] == "Error:":
                    manager.error(output)

    @staticmethod
    def _get_filesystems(manager, device):
        output = device.send("show filesystem")
        file_systems = {}
        start = False
        for line in output.split('\n'):
            if line.strip().endswith("Prefixes"):
                start = True
                continue
            if start:
                items = line.split()
                if len(items) == 5:
                    size, free, type, flags, fs_name, = line.split()
                    file_systems[fs_name] = {
                        'size': 0 if size == '-' else long(size),
                        'free': 0 if size == '-' else long(free),
                        'type': type,
                        'flags': flags,
                    }
                else:
                    continue
        return file_systems

    @staticmethod
    def _can_create_dir(manager, device, filesystem):

        def send_newline(ctx):
            ctx.ctrl.sendline()
            return True

        def error(ctx):
            ctx.message = "Filesystem error"
            return False

        def readonly(ctx):
            ctx.message = "Filesystem is readonly"
            return False


        test_dir = "rw_test"
        dir = filesystem + test_dir

        REMOVE_DIR = re.compile(re.escape("Remove directory filename [{}]?".format(test_dir)))
        DELETE_CONFIRM = re.compile(re.escape("Delete {}/{}[confirm]".format(filesystem, test_dir)))
        REMOVE_ERROR = re.compile(re.escape("%Error Removing dir {} (Directory doesnot exist)".format(test_dir)))
        CREATE_DIR = re.compile(re.escape("Create directory filename [{}]?".format(test_dir)))
        CREATED_DIR = re.compile(re.escape("Created dir {}/{}".format(filesystem, test_dir)))
        READONLY = re.compile(re.escape("%Error Creating Directory {}/{} (Read-only file system)".format(
            filesystem, test_dir)))

        command = "rmdir {}".format(dir)
        events = [device.prompt, REMOVE_DIR, DELETE_CONFIRM, REMOVE_ERROR, TIMEOUT]
        transitions = [
            (REMOVE_DIR, [0], 1, send_newline, 5),
            (DELETE_CONFIRM, [1], 2, send_newline, 5),
            # if dir does not exist initially it's ok
            (REMOVE_ERROR, [0], 2, None, 0),
            (device.prompt, [2], -1, None, 0),
            (TIMEOUT, [0, 1, 2], -1, error, 0)

        ]
        manager.log("Removing test directory from {} if exists".format(dir))
        if not device.run_fsm(DiskSpacePlugin.DESCRIPTION, command, events, transitions, timeout=5):
            return False

        command = "mkdir {}".format(dir)
        events = [device.prompt, CREATE_DIR, CREATED_DIR, READONLY, TIMEOUT]
        transitions = [
            (CREATE_DIR, [0], 1, send_newline, 5),
            (CREATED_DIR, [1], 2, send_newline, 5),
            (device.prompt, [2], -1, None, 0),
            (TIMEOUT, [0, 1, 2], -1, error, 0),
            (READONLY, [1], -1, readonly, 0)
        ]
        manager.log("Creating test directory on {}".format(dir))
        if not device.run_fsm(DiskSpacePlugin.DESCRIPTION, command, events, transitions, timeout=5):
            return False

        command = "rmdir {}".format(dir)
        events = [device.prompt, REMOVE_DIR, DELETE_CONFIRM, REMOVE_ERROR, TIMEOUT]
        transitions = [
            (REMOVE_DIR, [0], 1, send_newline, 5),
            (DELETE_CONFIRM, [1], 2, send_newline, 5),
            (REMOVE_ERROR, [0], -1, error, 0),
            (device.prompt, [2], -1, None, 0),
            (TIMEOUT, [0, 1, 2], -1, error, 0)

        ]
        manager.log("Removing test directory from {}".format(dir))
        if not device.run_fsm(DiskSpacePlugin.DESCRIPTION, command, events, transitions, timeout=5):
            return False

        return True

    @staticmethod
    def start(manager, device, *args, **kwargs):
        ctx = device.get_property("ctx")
        try:
            packages = ctx.software_packages
        except AttributeError:
            manager.error("No package list provided")

        try:
            server_repository_url = ctx.server_repository_url
        except AttributeError:
            manager.error("No repository path provided")

        file_systems = DiskSpacePlugin._get_filesystems(manager, device)

        disk0 = file_systems.get('disk0:', None)
        if not disk0:
            manager.error("No filesystem 'disk0:' on active RP")

        disk1 = file_systems.get('disk1:', None)

        if not disk1:
            manager.log("No filesystem 'disk1:' on active RP")

        for fs, values in file_systems.iteritems():
            if 'rw' not in values.get('flags'):
                manager.error("{} is not 'rw'".format(fs))

        if not DiskSpacePlugin._can_create_dir(manager, device, "disk0:"):
            manager.error("Can't create dir on disk0:")

        free_disk0 = disk0.get('free', 0)

        device.store_property('free_disk0_space', free_disk0)

        if server_repository_url is None:
            manager.log("Skipping calculation of required harddisk free space")
            return

        if server_repository_url[:4] == 'sftp':
            manager.log('Skipping as disk space check not supported for sftp')
            return

        total_size = 0
        for package in packages:
            if package == "":
                continue
            package_url = os.path.join(server_repository_url, package)
            size = DiskSpacePlugin._get_pie_size(device, package_url)
            total_size += size
            manager.log("Package: {} requires {} bytes".format(package_url, size))

        manager.log(
            "Total (required/available): {}/{} bytes".format(
                total_size,
                free_disk0
            )
        )
        if free_disk0 < total_size:
            manager.error("Not enough space on disk0: to install packages.")

        return True
