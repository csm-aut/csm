#! /usr/local/bin/python
from optparse import OptionParser
import sys
import datetime
import os
import main
from au.utils.file import get_urls_from_txt
from au.utils import pkglist


def execute(context,testing_csm = False):
    # Initialize the argument so it won't fail when Gunicorn invokes this function
    sys.argv = []
    oparser = OptionParser()
    options, args = oparser.parse_args()
    ctx = context
    print "Starting AU ....."
    options.device_url = ctx.host_urls[:]
    if hasattr(ctx,'server_repository_url'):
        options.repository_path = ctx.server_repository_url

    if hasattr(ctx,'software_packages'):
        options.pkg_file = ctx.software_packages

    options.logdir = context.log_directory
    options.outdir = context.log_directory
    options.migdir = context.migration_directory
    options.devices = None
    options.session_log = True
    options.device_verbose = 5
    options.verbose = 5
    options.max_threads = 1
    options.overwrite_logs = False
    options.delete_logs = False
    options.addset = False
    options.migrateset = False
    options.preupgradeset = False
    options.upgradeset = False
    options.removeset=False
    options.deactivateset=False
    options.postupgradeset = False
    options.commitset = False
    options.pkg_state = False
    options.cli_file = None
    options.turboboot = False
    options.ignore_errors = False
    if not os.path.exists(options.outdir) :
        try :
            os.makedirs(options.outdir)
        except IOError, e:
            parser.error(str(e))

    if not os.path.exists(options.logdir) :
        try :
            os.makedirs(options.logdir)
        except IOError, e:
            parser.error(str(e))

    if not os.path.exists(options.migdir) :
        try :
            os.makedirs(options.migdir)
        except IOError, e:
            parser.error(str(e))

    options.stdoutfile = open(os.path.join(options.logdir,'aut_output'),"w")
    print "="*80
    if ctx.requested_action == 'Install Add':
        options.addset = True

    elif ctx.requested_action == 'Pre-Upgrade':
        options.preupgradeset = True

    elif ctx.requested_action == 'Activate':
        options.upgradeset = True

    elif ctx.requested_action == 'Post-Upgrade':
        options.postupgradeset = True

    elif ctx.requested_action == 'Get-Package':
        options.pkg_state = True

    elif ctx.requested_action == 'Commit':
        options.commitset = True

    elif ctx.requested_action == 'Remove':
        options.removeset= True

    elif ctx.requested_action == 'Deactivate':
        options.deactivateset = True
    #   options.pkg_state = True
    elif ctx.requested_action == 'Migrate To eXR':
        options.migrateset = True

    options.ctx = ctx
    status = main.execute(options, args, oparser)
    print "AUT Execution completed with status :",status
    options.stdoutfile.close()
    if testing_csm :
        return options.ctx 
    return status


class Host(object):
    """
    Host class
    """
    def __init__(self):
        self.urls = []


class CsmContext(object):

    """
    CsmContext class contains all the information passed by CSM to AU .
    This is to test CSM AU interconnection.
    """

    def __init__(self,options):
        # Convert options to context
        if options.upgradeset :
            self.requested_action = 'Activate'
        elif options.preupgradeset :
            self.requested_action = 'Pre-Upgrade'
        elif options.addset :
            self.requested_action = 'Install Add'
        elif options.postupgradeset :
            self.requested_action = 'Post-Upgrade'
        elif options.pkg_state:
            self.requested_action = 'Get-Package'
        elif options.commitset :
            self.requested_action = 'Install Commit'
        elif options.deactivateset:
            self.requested_action='Deactivate'
        elif options.removeset:
            self.requested_action = 'Remove'
        elif options.migrateset:
            self.requested_action = 'Migrate To eXR'
        if options.repository_path :
            self.server_repository_url = options.repository_path
       
        self.host = Host()
        if options.device_url :
            self.host_urls = options.device_url[:]
        if options.devices:
            self.host_urls = get_urls_from_txt(options.devices,1)[:]

        if options.pkg_file and not options.repository_path : 
            self.server_repository_url = pkglist.get_repo(options.pkg_file)
        elif options.repository_path :
            self.server_repository_url = options.repository_path
        if options.pkg_file :
            self.software_packages = pkglist.get_pkgs(options.pkg_file)
        self.log_directory = options.logdir
        self.active_cli = None
        self.inactive_cli = None
        self.committed_cli = None

    def ctx(self):
        print "requested_action: ",self.requested_action
        print "host urls:",self.host_urls 
        print "software_packages:",self.software_packages
        print "log_directory:",self.log_directory
        print "server_repository_url :",self.server_repository_url
        return True


def csm_au_test(options):
    import sys
    options.addset = False
    context = CsmContext(options)
    sys.argv = []
    options = None
    ctx = execute(context,True)
    print "Active :"
    print ctx.active_cli
    print "Inctive :"
    print ctx.inactive_cli
    print "Committed:"
    print ctx.committed_cli 
    
