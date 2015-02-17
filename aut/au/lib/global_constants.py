#==============================================================================
# global_constants.py  -- definitions common to all plugins
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


import re
import pexpect


MAXREAD = 100000
SYSTEM_RELOADED = 1001
INSTALL_METHOD_RELOAD = SYSTEM_RELOADED
INSTALL_METHOD_PROCESS_RESTART = 1003

# Execution state
SUCCESS = 0
SKIPPED = 1
IGNORED = 2
NOT_NEEDED = 3
FAIL = -1

NO_PLUGINS = 1002
IOS = 'IOS'
IOS_XR = "IOS XR"
WINDOWSIZE = None
LOGIN_PROMPT = "#"
PROMPT = "#"
ROOT_PROMPT = "\#"
PERMISSION_DENIED = ".*enied|.*nvalid|.*ailed"
MODULUS_TO_SMALL = "modulus too small"
PROTOCOL_DIFFER = "Protocol major versions differ"
NEWSSHKEY = "Are you sure you want to continue connecting"
INVALID_INPUT = "Invalid input detected"
HOST_KEY_FAILED = "verification failed"
CONNECTION_REFUSED = "Connection refused"
RESET_BY_PEER = "reset by peer|closed by foreign host"
PASS = "Password:"
FIRST_LOGIN = "^]"
USERNAME = "Username: "
PRIVALEGE = re.compile(r"^\benable\b|^\ben\b|^\bsu\b")
MORE = "--more--|--More--|^\!"
EOF = pexpect.EOF
aulogger = None
tout = 20
# to cope with different platform putting this max
tout_cmd = 180
term = "both"
LOGIN_PROMPT_ERR = "% Invalid input detected at '^' marker."
AUTH_FAILED = "% Authentication failed"

pluging_string = {
    'PreUpgrade': "PreUpgrade Checks",
    'Upgrade': "Upgrade Started",
    'PostUpgrade': "PostUpgrade Checks"
}

active_node = ""
standby_node = ""


class bcolors:
    HEADER = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def initalize(self):
        self.HEADER = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''


class Term:
    BLUE = '\033[96m'
    GREEN = '\033[92m'
    MAGENTA = '\033[93m'
    RED = '\033[91m'
    NORMAL = '\033[0m'

    def initalize(self):
        self.BLUE = ''
        self.GREEN = ''
        self.MAGENTA = ''
        self.RED = ''
        self.NORMAL = ''

term = Term()


def print_failure(message):
    print message


def print_warning(message):
    print message


def print_success(message):
    print message


# TODO(klstanie) What is the reason to define those constants?
# Plugin types
TURBOBOOT = "TURBOBOOT"
UPGRADE = "UPGRADE"
PRE_UPGRADE = "PRE_UPGRADE"
POST_UPGRADE = "POST_UPGRADE"
PRE_UPGRADE_AND_POST_UPGRADE = "PRE_UPGRADE_AND_POST_UPGRADE"
PRE_UPGRADE_AND_UPGRADE = "PRE_UPGRADE_AND_UPGRADE"
UPGRADE_AND_POST_UPGRADE = "UPGRADE_AND_POST_UPGRADE"

supported_plugin_types = [
    PRE_UPGRADE,
    POST_UPGRADE,
    PRE_UPGRADE_AND_POST_UPGRADE,
    PRE_UPGRADE_AND_UPGRADE,
    UPGRADE_AND_POST_UPGRADE
]
