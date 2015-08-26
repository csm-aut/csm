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
from base import BaseHandler
from parsers.loader import get_package_parser_class 
from utils import import_module
import re

try:
    import condor 
except ImportError:
    pass

import time

AUT_PATH = '../aut'

class BaseConnectionHandler(BaseHandler):           
    def execute(self, ctx):
        global AUT_PATH
        
        csm_au_module = import_module('au.csm_au', AUT_PATH)
        if csm_au_module is not None:
            status = csm_au_module.execute(ctx)
            if status == 0 :
                ctx.success = True
        else:    
            try:
                conn = condor.make_connection_from_urls('host', ctx.urls)
                conn.connect()
                conn.disconnect()
                ctx.success = True        
            except:
                pass
        
class BaseInventoryHandler(BaseHandler):           
    def execute(self, ctx):
        global AUT_PATH
        
        csm_au_module = import_module('au.csm_au', AUT_PATH)
        if csm_au_module is not None:
            status = csm_au_module.execute(ctx)
            if status == 0 :
                self.get_software(ctx.host,
                    install_inactive_cli=ctx.inactive_cli, 
                    install_active_cli=ctx.active_cli, 
                    install_committed_cli=ctx.committed_cli)
                ctx.success = True
        else:
            try:
                conn = condor.make_connection_from_context(ctx)
                conn.connect()
                output = conn.send('show version')
                match = re.search('.vm',output)

                append = ' summary' if match else ''

                ctx.inactive_cli = conn.send('sh install inactive' + append)
                ctx.active_cli = conn.send('sh install active' + append)
                ctx.committed_cli = conn.send('sh install committed' + append)
                conn.disconnect()
 
                self.get_software(ctx.host,
                    install_inactive_cli=ctx.inactive_cli, 
                    install_active_cli=ctx.active_cli, 
                    install_committed_cli=ctx.committed_cli)
                ctx.success = True
            except:
                pass

    def get_software(self, host, install_inactive_cli, install_active_cli, install_committed_cli):
        package_parser_class = get_package_parser_class(host.platform)
        package_parser = package_parser_class()
        
        return package_parser.get_packages_from_cli(host,
            install_inactive_cli=install_inactive_cli, 
            install_active_cli=install_active_cli, 
            install_committed_cli=install_committed_cli)       
       
class BaseInstallHandler(BaseHandler):                         
    def execute(self, ctx):
        global AUT_PATH
        
        csm_au_module = import_module('au.csm_au', AUT_PATH)
        if csm_au_module is not None:
            status = csm_au_module.execute(ctx)
            if status == 0 :
                ctx.success = True   
        else:
            try:
                time.sleep(10)
                ctx.post_status('Copying files from TFTP server to host...')
                time.sleep(10)
                ctx.success = True
            except:
                pass
    

    
