# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
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

from handlers.loader import BaseHandler
from parsers.loader import get_package_parser_class 

import condoor

try:
    from csmpe import CSMPluginManager
    csmpe_installed = True
except ImportError:
    from horizon.plugin_manager import PluginManager
    csmpe_installed = False

import time
import os
import re


#import logging
#logging.basicConfig(
#        format='%(asctime)-15s %(levelname)8s: %(message)s',
#        level=logging.DEBUG)

class BaseInventoryHandler(BaseHandler):           
    def start(self, ctx):
        conn = condoor.Connection(ctx.host.hostname, ctx.host_urls, log_dir=ctx.log_directory)
        try:
            conn.discovery()
        except condoor.GeneralError as e:
            ctx.post_status = e.message
            return

        try:
            conn.connect()

            if conn.os_type == "XR":
                ctx.inactive_cli = conn.send('sh install inactive summary')
                ctx.active_cli = conn.send('sh install active summary')
                ctx.committed_cli = conn.send('sh install committed summary')
            elif conn.os_type == "eXR":
                ctx.inactive_cli = conn.send('sh install inactive')
                ctx.active_cli = conn.send('sh install active')
                ctx.committed_cli = conn.send('sh install committed')

            self.get_software(ctx)
            ctx.success = True

        except condoor.GeneralError as e:
            ctx.post_status = e.message

        finally:
            conn.disconnect()


    def get_software(self, ctx):
        package_parser_class = get_package_parser_class(ctx.host.software_platform)
        package_parser = package_parser_class()
        
        return package_parser.get_packages_from_cli(
            ctx.host,
            install_inactive_cli=ctx.inactive_cli,
            install_active_cli=ctx.active_cli,
            install_committed_cli=ctx.committed_cli
        )



class BaseInstallHandler(BaseHandler):                         
    def start(self, ctx):

        if csmpe_installed:
            pm = CSMPluginManager(ctx)
        else:
            pm = PluginManager()
        try:
            if csmpe_installed:
                pm.dispatch("run")
            else:
                pm.run(ctx)
        except condoor.GeneralError as e:
            ctx.post_status = e.message
            ctx.success = False