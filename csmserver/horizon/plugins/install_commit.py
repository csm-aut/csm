# =============================================================================
# install_commit.py - plugin for adding packages
#
# Copyright (c)  2013, Cisco Systems
# All rights reserved.
#
# Author: Prasad S R
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

from plugin import IPlugin
from ..plugin_lib import get_package, watch_operation


class InstallCommitPlugin(IPlugin):
    """
    A plugin for install commit operation
    """
    NAME = "INSTALL_COMMIT"
    DESCRIPTION = "Install Commit Packages"
    TYPE = "COMMIT"
    VERSION = "1.0.0"
    FAMILY = ["ASR9K"]

    @staticmethod
    def start(manager, device, *args, **kwargs):
        """
        It performs commit operation 
        """

        failed_oper = r'Install operation (\d+) failed'
        completed_with_failure = 'Install operation (\d+) completed with failure'
        success_oper = r'Install operation (\d+) completed successfully'

        cmd = "admin install commit"
        output = device.send(cmd)
        result = re.search('Install operation (\d+) \'', output)
        if result:
            op_id = result.gropup(1)
            watch_operation(manager, device, op_id)
        else:
            manager.error("Operation ID not found")

        cmd = "admin show install log {} detail".format(int(op_id))
        output = device.send(cmd)

        if re.search(failed_oper, output):
            manager.error("Install operation failed")

        if re.search(completed_with_failure, output):
            manager.log("Completed with failure but failure was after Point of No Return")

        elif re.search(success_oper, output):
            manager.log("Install Commit was Successful")

        get_package()

