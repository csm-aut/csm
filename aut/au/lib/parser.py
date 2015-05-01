#==============================================================================
# parser.py -- parser for accelerated upgrade CLI
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


import sys
import os
import optparse
import getpass
import urlparse
from au.utils import pkglist


def parsecli():

    oparser = optparse.OptionParser()

    oparser.add_option(
        "--url",
        dest="device_url",
        default=None,
        metavar="telnet|ssh://[user:pass@]a.b.c.d[:port]",
        help="The device url to run this tool against.\n"
        "--url telnet://cisco:cisco@1.2.3.4:2004")

    oparser.add_option(
        '--urls',
        dest='devices',
        metavar='TextFile',
        default=None,
        help='Text file containing one URL per line')

    oparser.add_option(
        "-r",
        "--repository",
        type="string",
        dest="repository_path",
        default=None,
        metavar="URL",
        help="url where packages are stored[Mandatory]")

    oparser.add_option(
        "-f",
        "--pkg_file_list",
        type="string",
        dest="pkg_file",
        default=None,
        metavar="FILE",
        help="File which contains list of packages [Mandatory]")

    oparser.add_option(
        "-c",
        dest="cli_file",
        default=None,
        metavar="FILE",
        help="File which contains list of commands to backup")

    oparser.add_option(
        "--pre-upgrade",
        action="store_true",
        dest="preupgradeset",
        default=False,
        metavar=" ",
        help="Run only Pre upgrade checks")

    oparser.add_option(
        "--post-upgrade",
        action="store_true",
        dest="postupgradeset",
        default=False,
        metavar=" ",
        help="Run only Post-upgrade checks, Note : Plugins which depend on "
        "data collected during pre upgrade checks to verify will fail ,"
        " but execution will not be blocked")

    oparser.add_option(
        "--upgrade",
        action="store_true",
        dest="upgradeset",
        default=False,
        metavar=" ",
        help="do an upgrade without running pre and post upgrade checks")

    oparser.add_option(
        "--commit",
        action="store_true",
        dest="commitset",
        default=False,
        metavar=" ",
        help="do install commit")

    oparser.add_option(
        "--turboboot",
        action="store_true",
        dest="turboboot",
        default=False,
        metavar=" ",
        help="execute turboboot (need console login)")

    # oparser.add_option(
    #    "-m",
    #    "--mail",
    #    dest    = "mail",
    #    default = None,
    #    metavar = 'ADDRESS',
    #    help    = "E-mail address to send a notice at the end of processing. "
    #         "e.g.: -m foo@cisco.com.")

    oparser.add_option('--logdir',
                       dest='logdir',
                       metavar='DIR',
                       default='aulogs',
                       help='Logs any communication into the directory with '
                       'the given name. Each filename consists of the '
                       'hostname with ".log" appended. Errors are '
                       'written to a separate file, where the filename '
                       'consists of the hostname with ".log.error" '
                       'appended.'.strip())

    oparser.add_option('--outdir',
                       dest='outdir',
                       default='au_out',
                       metavar='DIR',
                       help='Store the configuration and commands output into '
                       'given directory name. Each filename consists of'
                       'of the hostname with datetime stamp'.strip())

    oparser.add_option('--delete-logs',
                       dest='delete_logs',
                       action='store_true',
                       default=False,
                       help='Delete logs of successful operations when done.')

    oparser.add_option('--overwrite-logs',
                       dest='overwrite_logs',
                       action='store_true',
                       default=False,
                       help='Instructs AU to overwrite existing logfiles. '
                       'The default is to append the output if a '
                       'log already exists.'.strip())

    oparser.add_option('--verbose',
                       dest='verbose',
                       type='int',
                       metavar='NUM',
                       default=1,
                       help='Print out debug information about the job queue. '
                       'NUM is a number between 0 (min) '
                       'and 5 (max). Default is 0.'.strip())

    oparser.add_option('--device-verbose',
                       dest='device_verbose',
                       type='int',
                       metavar='NUM',
                       default=0,
                       help='Print out debug information about the device '
                       'activity. NUM is a number between 0 (min) '
                       'and 5 (max). Default is 0.'.strip())

    oparser.add_option('--session-log',
                       dest='session_log',
                       action='store_true',
                       default=True,
                       help='Log device sesssion information to the '
                       'file in logdir'.strip())

    oparser.add_option('--ignore-errors',
                       dest='ignore_errors',
                       action='store_true',
                       default=False,
                       help='Ignore plugin errors. By default if execution of '
                       'any plugin fails the device is excluded '
                       'from further processing'.strip())

    oparser.add_option('--max-threads',
                       dest='max_threads',
                       type='int',
                       metavar='NUM',
                       default=5,
                       help='Maximum concurrent threads running per plugin. '
                       'Default is 1'.strip())

    oparser.add_option('--pkg-state',
                       dest="pkg_state",
                       action='store_true',
                       default=False,
                       help='Connect to the device and get active/inactive/committed packages')

    oparser.add_option('--ISSU',
                       action  = "store_true",
                       dest    = "issu",
                       default = False,
                       metavar = " ",
                       help    = "Perform ISSU upgrade of ncs6k")


    options, args = oparser.parse_args()
    check_options(options)

    if os.path.exists('test_csm'):
        testcsm(options)
    return options, args, oparser

def testcsm(options):
    from au import csm_au
    csm_au.csm_au_test(options)

    # Retuning non zero as this is only for test and shoule never be used 
    sys.exit("CSM test execution complete")

def get_user_input(msg):
    dev_password = getpass.getpass("\n" + msg)
    # Try again if CR was pressed ..
    if not dev_password:
        dev_password = getpass.getpass(msg)
    return dev_password.strip()


def fix_repo_password(options):
    repo_url = options.repository_path
    u = urlparse.urlparse(repo_url)
    if u.scheme == "tftp":
        return
    if not u.username:
        print "Username is missing in repository URL"
        sys.exit(-1)
    if not u.password:
        repo_password = get_user_input(
            "%s://%s@%s Password:" % (u.scheme, u.username, u.hostname))
        list_url = list(u[:])
        list_url[1] = list_url[1].replace(
            u.username, "%s:%s" % (u.username, repo_password))
        options.repository_path = urlparse.urlunparse(tuple(list_url))
        return


def get_repo_from_file(txtfile):
    return pkglist.get_repo(txtfile)


def check_options(options):
    status = True
    if options.pkg_state :
        #this options should be just this nothing else
        assert(options.device_url or options.devices )
        assert(not options.preupgradeset)
        assert(not options.postupgradeset)
        assert(not options.upgradeset)
        return
    if not options.device_url and not options.devices:
        print("Mandatory option '--url' or '--urls' is missing")
        status = False

    if not options.pkg_file and not options.postupgradeset:
        print("Mandatory option ' -f ' is  missing")
        status = False

    if not options.repository_path and not options.postupgradeset and not options.upgradeset:
        # Check if repo is not given package list file
        if not options.pkg_file:
            print("Mandatory option '-r ' is  missing")
            status = False
        else:
            repo_path = get_repo_from_file(options.pkg_file)
            if not repo_path:
                print("Mandatory option '-r ' is  missing")
                status = False
            else:
                options.repository_path = repo_path
    if options.repository_path:
        # If repo path is tftp or sftp , and not having password , get the
        # password
        fix_repo_password(options)

    if options.preupgradeset and options.postupgradeset:
        print(
            "--pre-upgrade and --post-upgrade options are mutually exclusive")

    if options.cli_file:
        if not os.path.exists(options.cli_file):
            print "Command file specified {} does not exists".format(options.cli_file)
            status = False
    if not status:
        sys.exit(-1)
    return 0
