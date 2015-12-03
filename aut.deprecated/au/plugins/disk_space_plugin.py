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

from au.plugins.plugin import IPlugin
from au.utils import pkglist


class DiskSpacePlugin(IPlugin):

    """
    Pre-upgrade check
    This plugin checks the available disk space
    """
    NAME = "DISK_SPACE"
    DESCRIPTION = "Disk Space Check"
    TYPE = "PRE_UPGRADE"
    VERSION = "0.1.1"

    def _get_pie_size(self, device, package_url):
        cmd = "admin show install pie-info " + package_url

        success, output = device.execute_command(cmd)
        if success:
            for line in output.split('\n'):
                if "Compressed" in line:
                    size = long(line.split(":")[1].strip())
                    return size
                if line and line[:6] == "Error:":
                    self.error(output)

        self.error("Command error: {}".format(cmd))

    def _get_filesystems(self, device):
        success, output = device.execute_command("show filesystem")
        success, output = device.execute_command("show filesystem")
        if not success:
            self.error("Show filesystem command failed.")
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

    def _can_create_dir(self, device, filesystem):

        test_dir = "rw_test"
        dir = filesystem + test_dir
        success, output = device.execute_command(
            "mkdir {}".format(dir),
            timeout=5,
            wait_for_string="Create directory filename [{}]?".format(test_dir)
        )
        if not success:
            return False
        # Confirm by sending CR and waiting for prompt
        success, output = device.execute_command()
        if not success:
            return False

        success, output = device.execute_command(
            "rmdir {}".format(dir),
            timeout=5,
            wait_for_string="Remove directory filename [{}]?".format(
                test_dir)
        )
        if not success:
            return False

        success, output = device.execute_command("\n")
        if not success:
            return False

        return True

    def start(self, device, *args, **kwargs):

        file_systems = self._get_filesystems(device)

        disk0 = file_systems.get('disk0:', None)
        if not disk0:
            self.error("No filesystem 'disk0:' on active RP")

        disk1 = file_systems.get('disk1:', None)
        if not disk1:
            self.log("No filesystem 'disk1:' on active RP")

        for fs, values in file_systems.iteritems():
            if 'rw' not in values.get('flags'):
                self.error("{} is not 'rw'".format(fs))

        if not self._can_create_dir(device, "disk0:"):
            self.error("Can't create dir on disk0:")

        free_disk0 = disk0.get('free', 0)

        repository_path = kwargs.get("repository", None)

        if not repository_path:
            self.error("No repository path provided")

        if repository_path[:4] == 'sftp':
            self.log('Skipping as disk space check not supported for sftp')
            return

        pkg_file = kwargs.get("pkg_file", None)
        if not pkg_file:
            self.error("No package list file provided.")

        packages = pkglist.get_pkgs(pkg_file)
        total_size = 0
        for package in packages:
            package_url = os.path.join(repository_path, package)
            size = self._get_pie_size(device, package_url)
            total_size += size
            self.log("Package: {} requires {} bytes".format(package_url, size))

        self.log(
            "Total (required/available): {}/{} bytes".format(
                total_size,
                free_disk0
            )
        )
        if free_disk0 < total_size:
            self.error("Not enough space on disk0: to install packages.")

        return True
