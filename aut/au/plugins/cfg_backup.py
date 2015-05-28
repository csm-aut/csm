# =============================================================================
# cfg_backup.py  - Plugin to capture(show running)
# configurations present on the system.
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


from au.plugins import IPlugin
import os


class ConfigBackupPlugin(IPlugin):

    """
    Pre-upgrade check
    This plugin checks and record active packages
    """
    NAME = "CONFIG_BACKUP"
    DESCRIPTION = "Configuration Backup"
    TYPE = "PRE_UPGRADE"
    VERSION = "0.1.1"

    def start(self, device, *args, **kwargs):

        name = "{}.log".format(self.NAME.lower())
        fname = os.path.join(device.output_store_dir, name)
        try:
            fd_name = open(fname, 'w')
        except:
            self.error("Failed to open %s file to write " % (fname))
        cmd = "show running"
        success, output = device.execute_command(cmd,timeout=300)
        if not success:
            fd_name.close()
            self.error("Configuration backup failed")
        else:
            fd_name.write(cmd)
            fd_name.write(output)
        return True
