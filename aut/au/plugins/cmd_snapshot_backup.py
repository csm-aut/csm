# =============================================================================
# cmd_snapshot_backup.py - Plugin for taking command backups.
#
# Copyright (c)  2013, Cisco Systems
# All rights reserved.
#
# Suryakant Kewat
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


from au.lib.global_constants import *
from au.plugins.plugin import IPlugin

import codecs

INVALID = '% Invalid input detected at'


class CommandSnapshotPlugin(IPlugin):

    """
    Pre-upgrade and Post-upgrade check
    This plugin collects all CLI provided in file
    """
    NAME = "CMD_SNAPSHOT"
    DESCRIPTION = "Backup Command Snapshots"
    TYPE = "PRE_UPGRADE_AND_POST_UPGRADE"
    VERSION = "0.0.1"

    def start(self, device, *args, **kwargs):

        cmd_file = kwargs.get('cmd_file', None)
        if not cmd_file:
            return True

        with codecs.open(cmd_file, 'r', "utf-8") as f:
            for line in f:
                cmd = line.strip()
                success, output = device.execute_command(cmd)
                if not success:
                    print("CMD execution error: {}".format(cmd))

        return
