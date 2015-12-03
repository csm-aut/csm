# =============================================================================
# cfg_consistency.py plugin to check config consistency
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
from au.plugins.plugin import IPlugin
import au.lib.pkg_utils as pkgutils


class ConfigConsistencyPlugin(IPlugin):

    """
    This plugin commits the upgraded software and checks config consistency
    """
    NAME = "CONFIG_CONSISTENCY"
    DESCRIPTION = "Configuration Consistency Check"
    TYPE = "POST_UPGRADE"
    VERSION = "0.0.1"

    def start(self, device, *args, **kwargs):
        """
        Start the plugin

        """
        no_valid_redundancy = 'Node \w+/\w+/\w+ has no valid partner'
        valid_redundancy = 'Node Redundancy Partner \(\w+/\w+/\w+\) is in .+ role'
        failed_oper = r'Install operation (\d+) failed'

        name = "{}.log".format(self.NAME.lower())
        fname = os.path.join(device.output_store_dir, name.replace(":", "_"))
        try:
            fd_fname = open(fname, 'w')
        except:
            self.error("Failed to open %s file to write " % (fname))

        cmd = "admin show platform"
        success, output = device.execute_command(cmd)
        if success:
            inventory = pkgutils.parse_xr_show_platform(output)
            if not pkgutils.validate_xr_node_state(inventory, device):
                fd_fname.close()
                self.error("All nodes are not in right state:\n %s" % (output))

            # Save what was verified
            fd_fname.write(cmd)
            fd_fname.write(output)

        # Verify show redundancy
        cmd = "admin show redundancy"
        success, output = device.execute_command(cmd)

        if re.search(valid_redundancy, output) or re.search(no_valid_redundancy, output):
            fd_fname.write(cmd)
            fd_fname.write(output)
        else:
            fd_fname.close()
            self.error("Redundancy check failed :\n%s" % (output))

        # Commit the installed software now
        #cmd = "admin install commit"
        #success, output = device.execute_command(cmd)
        #if not success or re.search(failed_oper, output):
        #    fd_fname.close()
        #    self.error("Instal commit failed:\n%s" % (output))

        # Store the state of packages after install
        cmd = "admin show install active"
        success, output = device.execute_command(cmd)
        if success:
            fd_fname.write(cmd)
            fd_fname.write(output)

        cmd = "admin show install inactive"
        success, output = device.execute_command(cmd)
        if success:
            fd_fname.write(cmd)
            fd_fname.write(output)

        cmd = "admin show install commit"
        success, output = device.execute_command(cmd)
        if success:
            fd_fname.write(cmd)
            fd_fname.write(output)

        # Show configuration failed startup
        cmd = "show configuration failed startup"
        success, output = device.execute_command(cmd)
        if success and len(output.split("\n")) > 4:
            fd_fname.close()
            self.warning("Fialed configs check {} {}".format(cmd, output))
            return False

        # TBD
        # 1. Clear config inconsistency
        # 2. install verify package / install verify package repair
        # 3. Cfs check
        # 4. mirror location 0/RSP0/CPU0 disk0:disk1:
        return True
