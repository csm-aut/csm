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


import commands
import os
from sys import stdout

import au.lib.global_constants
from au.lib.global_constants import *
from au.plugins.plugin import IPlugin
from au.utils import pkglist
from au.plugins.package_state import get_package


STAGING_DEVICE = "."
COPY_CMD = "cp"


class InstallCommitPlugin(IPlugin):
    """
    A plugin for install commit operation
    """
    NAME = "INSTALL_COMMIT"
    DESCRIPTION = "Install Commit Packages"
    TYPE = "COMMIT"
    VERSION = "0.0.1"

    def watch_operation(self, device, oper_id=0):
        """
        Function to keep watch on progress of operation

        """
        no_oper = r'There are no install requests in operation'
        in_oper = r'The operation is (\d+)% complete'
        success_oper = r'Install operation (\d+) completed successfully'
        completed_with_failure = 'Install operation (\d+) completed with failure'
        failed_oper = r'Install operation (\d+) failed'

        cmd = "admin show install request "

        # Wait untill install op completes, start the progress from
        # newline 

        stdout.write("\n\r")
        while 1:
            success, output = device.execute_command(cmd)
            if success and no_oper in output:
                # operation completed
                break
            elif success and re.search(in_oper,output):
                progress = re.search(
                            'The operation is (\d+)% complete', output).group(0)
                stdout.write("%s \r" % (progress))
                stdout.flush()
                continue
        
        # Ensure operation success
        cmd = "admin show install log %d detail" % int(oper_id)
        success, output = device.execute_command(cmd)
                        
        if not success or re.search(failed_oper, output):
             self.error(output)
                                                 
        if success and re.search(completed_with_failure, output):
             # Completed with failure but failure was after PONR
             print "Install commit completed with error"
        elif success and re.search(success_oper, output):
             print "Install commit completed"

        return True
                                                                                                                         
    def install_commit(self, device, kwargs):
        """
        It performs commit operation 
        """
        cmd = "admin install commit"
        success, output = device.execute_command(cmd)
        if success :
            op_id = re.search('Install operation (\d+) \'', output).group(1)
            self.watch_operation(device,op_id)
        else :
            self.error("Command :%s \n%s"%(cmd,output))
            
        get_package(device)
        return True

    def start(self, device, *args, **kwargs):
        """
        Start the plugin
        Return False if the plugin has found a fatal error, True otherwise.

        """
        return self.install_commit(device, kwargs)
