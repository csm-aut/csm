# =============================================================================
# install_add.py - plugin for adding packages
#
# Copyright (c)  2013, Cisco Systems
# All rights reserved.
#
# Author: Suryakant Kewat
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
import time
from sys import stdout

import au.lib.global_constants
from au.lib.global_constants import *
from au.plugins.plugin import IPlugin
from au.utils import pkglist
from au.plugins.package_state import get_package


STAGING_DEVICE = "."
COPY_CMD = "cp"


class InstallAddPlugin(IPlugin):
    """
    A plugin for add operation
    it will create xml equivalent for
    add operation. 
    Arguments:
    1.one argument of type dictionary
    """
    NAME = "INSTALL_ADD"
    DESCRIPTION = "Install Add Packages"
    TYPE = "ADD"
    VERSION = "0.0.1"

    def watch_operation(self, device, op_id=0):
        """
        Function to keep watch on progress of operation
        and report KB downloaded.

        """
        inst_op = "downloaded: Download in progress"
        pat_no_install = r'There are no install requests in operation'
        failed_oper = r'Install operation (\d+) failed'
        cmd = "admin show install request "

        # Wait untill install op completes, start the progress from
        # newline 
        stdout.write("\n\r")
        while 1:
            time.sleep(5)
            success, output = device.execute_command(cmd)
            if success and inst_op in output :
                downloaded = re.search('(.*)KB downloaded: Download in progress', output).group(0)
                if downloaded :
                    stdout.write("%s \r" % downloaded.strip())
                    stdout.flush()
                continue 
            elif success and pat_no_install in output :
                break
        if op_id :
            # Ensure operation was success
            cmd = "admin show install log %d detail" % int(op_id)
            success, output = device.execute_command(cmd)
            if not success or re.search(failed_oper, output):
                self.error(output)


        return True

    def update_csm_context(self, add_id, device, input_has_tar):
        """
       put install add id into csm context
        """
        csm_ctx = device.get_property('ctx')
        if csm_ctx :
           if hasattr(csm_ctx, 'operation_id'):
              if input_has_tar is True:
                 csm_ctx.operation_id = add_id
                 self.log("Update Install Add ID to CSM ctx")
              else :
                 csm_ctx.operation_id = None
        # for non CSM case 
        else :
          if input_has_tar is True:
             device.store_property('operation_id', add_id)
          else:
             device.store_property('operation_id', None)


    def install_add(self, device, kwargs):
        """
        It performs add operation of the pies listed in given file
        """
        file_list = ""
        error_str = "Error:  "
        input_has_tar = False


        repo_str = kwargs.get('repository', None)
        if not repo_str:
            self.error("ERROR:repository not provided")

        pkg_name_list = kwargs.get('pkg_file',None)
        if kwargs.get('turbo_boot',None) and not pkg_name_list :
            # It's okay to have package list empty in case of TB as just vm is used for TB
            # This is not treated as  failure 
            return True

        if not pkg_name_list :
            self.error("Empty packages list ..")
            return False
      
        # skip vm image that's used only in TB
        for pkg in pkg_name_list :
            if pkg.find('.vm-') >= 0:
                pkg_name_list.remove(pkg)
            if pkg.find('.tar') >=0:
                input_has_tar = True
            else :
              if pkg.find('.pie') ==-1:
                 pkg_name_list.remove(pkg)

        packages = " ".join(pkg_name_list) 
        cmd = "admin install add source %s %s async" % (repo_str, packages)

        success, output = device.execute_command(cmd,timeout=7200)
        if success and error_str not in output:
            op_id = re.search('Install operation (\d+) \'', output).group(1)
            self.watch_operation(device,op_id)
            self.update_csm_context(op_id, device, input_has_tar)
        else :
            self.error("Command :%s \n%s"%(cmd,output))
            
        get_package(device)
        return True

    def start(self, device, *args, **kwargs):
        """
        Start the plugin
        Return False if the plugin has found a fatal error, True otherwise.

        """
        return self.install_add(device, kwargs)
