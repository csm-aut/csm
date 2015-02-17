# =============================================================================
# controllers
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

import logging

from time import sleep

import pexpect

from ..utils import to_list
from ..utils import delegate

from ..controllers.protocols import make_protocol
from ..exceptions import ConnectionError

_logger = logging.getLogger(__name__)


# Delegate following methods to _session class
@delegate("_session", ("expect", "expect_exact", "sendline",
                       "isalive", "sendcontrol", "send"))
class Controller(object):

    def __init__(self,
                 hostname,
                 hosts,
                 account_manager=None,
                 max_attempts=3,
                 logfile=None):

        self.hosts = to_list(hosts)
        self.max_attempts = max_attempts
        self.account_mgr = account_manager
        self.session_log = logfile
        self.hostname = hostname

        self.connected = False
        self._session = None

    @property
    def before(self):
        """
        Property added to imitated pexpect.spawn class
        """
        return self._session.before if self._session else None

    @property
    def after(self):
        """
        Property added to imitated pexpect.spawn class
        """
        return self._session.after if self._session else None

    def connect(self):
        connected = False
        for hop, host in enumerate(self.hosts, start=1):
            if not host.is_valid():
                raise ConnectionError("Invalid host", host)
            attempt = 1
            while attempt <= self.max_attempts:
                if not host.is_reachable():
                    self._dbg(40, "[{}] {}: Host not reachable".format(
                        hop, host.hostname)
                    )
                else:
                    protocol = make_protocol(
                        self,
                        host,
                        self.account_mgr,
                        self.session_log
                    )
                    self._dbg(
                        10,
                        "[{}] {}: Connecting. Attempt ({}/{})".format(
                            hop, host.hostname,
                            attempt, self.max_attempts
                        )
                    )
                    try:
                        connected = protocol.connect()
                    except:
                        self._dbg(
                            40,
                            "Error during connecting to target device")
                        self.disconnect()
                        raise

                    if connected:
                        break

                attempt += 1
                sleep(2)
            else:
                self._dbg(
                    40,
                    "[{}] {}: Connection error. "
                    "Max attempts reached.".format(
                        hop, host.hostname
                    )
                )
                self.disconnect()
                raise ConnectionError(host=self.hostname)

            self._dbg(
                20,
                "[{}] {}: Connected successfully".format(
                    hop, host.hostname
                )
            )

        if connected:
            self._dbg(20, "Connected target device")
            self.connected = True

        return connected

    def disconnect(self):
        """
        Gracefully disconnect from all the nodes
        """
        self._dbg(10, "Initializing the disconnection process")
        if self._session and self.isalive():
            self._dbg(10, "Disconnecting the sessions")
            index = 0
            hop = 0
            while index != 1 and hop < 10:
                self.sendline('exit')
                index = self.expect(
                    [pexpect.TIMEOUT, pexpect.EOF, "con.*is now available"],
                    timeout=2
                )
                if index == 1:
                    break

                if index == 2:  # console connected through TS
                    self._dbg(10, "Console connection detected")
                    self.sendline('\x03')
                    self.sendcontrol(']')
                    self.sendline('quit')

                hop += 1

        self._session.close()
        self._dbg(20, "Disconnected")

    def _dbg(self, level, msg):
        _logger.log(
            level, "[{}]: pexpect_ctrl: {}".format(self.hostname, msg)
        )
