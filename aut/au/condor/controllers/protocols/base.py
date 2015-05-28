# =============================================================================
# protocol
#
# Copyright (c)  2014, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
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


#INVALID_INPUT = "Invalid input detected"
PASS = "[P|p]assword:\s*"
XR_PROMPT = re.compile('(\w+/\w+/\w+/\w+:.*?)(\([^()]*\))?#')
USERNAME = "[U|u]sername:\s?|\nlogin:\s?"
PERMISSION_DENIED = "Permission denied"
AUTH_FAILED = "Authentication failed|not authorized|Login incorrect"
SHELL_PROMPT = "\$\s?|>\s?|#\s?|AU_PROMPT"
CONNECTION_REFUSED = "Connection refused"
RESET_BY_PEER = "reset by peer|closed by foreign host"

# Error when the hostname can't be resolved or there is
# network reachability timeout
UNABLE_TO_CONNECT = "nodename nor servname provided, or not known" \
                    "|Unknown host|[Operation|Connection] timed out"


class Protocol(object):

    def __init__(
            self,
            controller,
            node_info,
            account_manager=None,
            logfile=None,
            debug=5
    ):
        self.protocol = node_info.protocol
        self.hostname = node_info.hostname
        self.port = node_info.port
        self.password = node_info.password

        self.ctrl = controller
        self.logfile = logfile
        self.account_manager = account_manager

        username = node_info.username
        if not username and self.account_manager:
            username = self.account_manager.get_username(self.hostname)

        self.username = username
        self.debug = debug

    def _spawn_session(self, command):
        self.ctrl._dbg(10, "Starting session: '{}'".format(command))
        if self.ctrl._session and self.ctrl.isalive():
            self.ctrl.sendline(command)
        else:
            self.ctrl._session = pexpect.spawn(
                command,
                maxread=50000,
                searchwindowsize=None,
                echo=False
            )
            self.ctrl._session.logfile_read = self.logfile

    def connect(self):
        raise NotImplementedError("Connection method not implemented")

    def _dbg(self, level, msg):
        self.ctrl._dbg(level, "{}: {}".format(self.protocol, msg))

    def _acquire_password(self):
        password = self.password
        if not password:
            if self.account_manager:
                self.ctrl._dbg(
                    20,
                    "{}: {}: Acquiring password for {} "
                    "from system KeyRing".format(
                        self.protocol, self.hostname, self.username)
                )
                password = self.account_manager.get_password(
                    self.hostname,
                    self.username,
                    interact=True
                )
                if not password:
                    self.ctrl._dbg(
                        30,
                        "{}: {}: Password for {} does not exists "
                        "in KeyRing".format(
                            self.protocol, self.hostname, self.username)
                    )
        return password
