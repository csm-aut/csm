from base import BaseHandler
from parsers.loader import get_package_parser_class 
from utils import import_module

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
                ctx.inactive_cli = conn.send('sh install inactive summary')
                ctx.active_cli = conn.send('sh install active summary')
                ctx.committed_cli = conn.send('sh install committed summary')       
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
    

    
