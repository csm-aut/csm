# =============================================================================
# telnet
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

from base import *

from ...exceptions import \
    ConnectionAuthenticationError, \
    ConnectionError

# Telnet connection initiated
ESCAPE_CHAR = "Escape character is"
# Connection refused i.e. line busy on TS
CONNECTION_REFUSED = "Connection refused"
# Console connection
PRESS_RETURN = "Press RETURN to get started"


_logger = logging.getLogger(__name__)


class Telnet(Protocol):
    def __init__(self, controller, device, account_manager, logfile):
        super(Telnet, self).__init__(controller,
                                     device,
                                     account_manager,
                                     logfile)
        command = "telnet {} {}".format(
            self.hostname, self.port
        )

        self._spawn_session(command)

    def connect(self):
        state = 0
        transition = 0
        event = 0
        failed = False
        max_transitions = 10
        timeout = 300  # TIME FOR TELNET CONNECTION BEFORE ERROR

        while not failed and transition < max_transitions + 1:
            transition += 1
            event = self.ctrl.expect(
                [ESCAPE_CHAR, USERNAME, PASS, XR_PROMPT, SHELL_PROMPT,
                 PRESS_RETURN, UNABLE_TO_CONNECT,
                 CONNECTION_REFUSED, RESET_BY_PEER, PERMISSION_DENIED,
                 AUTH_FAILED, pexpect.TIMEOUT, pexpect.EOF],
                timeout=timeout, searchwindowsize=80
            )
            self._dbg(10, "{}: EVENT={}, STATE={}, TRANSITION={}".format(
                self.hostname, event, state, transition
            ))
            timeout = 60
            if event == 0:  # ESCAPE_CHARACTER
                if state == 0:
                    state = 1
                    timeout = 20
                    self._dbg(
                        10,
                        "{}: Waiting {} sec for initial response".format(
                            self.hostname, timeout)
                    )
                    continue
                else:
                    raise ConnectionError("Unexpected session init")

            if event == 1:  # USERNAME
                if state in [0, 1, 2]:
                    self._dbg(
                        10,
                        "{}: Sending username: '{}'".format(
                            self.hostname, self.username)
                    )
                    self.ctrl.sendline(self.username)
                    state = 3
                    timeout = 10
                    continue
                if state == 3:
                    self._dbg(
                        20,
                        "{}: Duplicate username request. "
                        "Ignoring.".format(self.hostname)
                    )
                if state == 4:
                    self._dbg(
                        20,
                        "{}: Expected prompt but username request "
                        "received ".format(self.hostname)
                    )
                    self.disconnect()
                    raise ConnectionAuthenticationError(host=self.hostname)

            if event == 2:  # PASS
                if state in [1, 2, 3]:  # if waiting for pass send pass
                    password = self._acquire_password()
                    if password:
                        self._dbg(
                            10,
                            "{}: Sending password: '***'".format(self.hostname)
                        )
                        self.ctrl.sendline(password)
                    else:
                        self.disconnect()
                        raise ConnectionAuthenticationError(
                            "Password not provided", self.hostname)

                    state = 4  # move to wait for prompt
                    timeout = 30
                continue

            if event == 3:  # XR PROMPT
                if state in [1, 2, 4]:
                    self._dbg(
                        10,
                        "{}: Received XR prompt".format(self.hostname)
                    )
                    break  # successfully got prompt
                if state == 7:
                    self._dbg(
                        10,
                        "{}: Received XR prompt after "
                        "connection failure".format(self.hostname)
                    )
                    return False

            if event == 4:  # SHELL PROMPT
                if state in [2, 4, 5, 6]:
                    self._dbg(
                        10,
                        "{}: Received Shell/Unix prompt".format(self.hostname)
                    )
                    break  # successfully got prompt
                if state == 7:
                    self._dbg(
                        10,
                        "{}: Received shell prompt after "
                        "connection failure".format(self.hostname)
                    )
                    return False

                self._dbg(
                    10,
                    "{}: Session output classified as shell "
                    "prompt, but not expected.".format(self.hostname)
                )
                continue

            if event == 5:  # PRESS_RETURN
                if state in [1, 2]:
                    self._dbg(
                        30,
                        "{}: Terminal server press "
                        "return ".format(self.hostname)
                    )
                    self.ctrl.send('\r\n')
                    continue

            if event == 6:  # UNABLE_TO_CONNECT
                if state == 0:
                    self._dbg(30, "{}: Unable to connect".format(self.hostname))
                    state = 7
                    timeout = 10
                    continue

            if event == 7:  # CONNECTION REFUSED
                raise ConnectionError("Connection refused", self.hostname)

            if event == 8:  # RESET_BY_PEER
                raise ConnectionError(
                    "Connection reset by peer", self.hostname)

            if event == 9:  # PERMISSION_DENIED
                self._dbg(
                    30,
                    "{}: Permission denied.".format(self.hostname)
                )
                raise ConnectionAuthenticationError(
                    "Permission denied", self.hostname)

            if event == 10:  # AUTH_FAILED
                if state == 4:
                    self.disconnect()
                    raise ConnectionAuthenticationError(
                        "Authentication failed", self.hostname)

            if event == 11:  # TIMEOUT
                if state == 1:
                    self._dbg(
                        30,
                        "{}: Connection timed out waiting for "
                        "initial response".format(self.hostname)
                    )
                    self._dbg(30, "{}: Sending CR/LF".format(self.hostname))
                    self.ctrl.send("\r\n")
                    state = 2
                    timeout = 10
                    continue

                if state == 4:
                    self._dbg(
                        10,
                        "{}: Setting 'PS1=AU_PROMPT'".format(self.hostname)
                    )
                    self.ctrl.sendline('PS1="{}"'.format("AU_PROMPT"))
                    state = 5
                    timeout = 5
                    continue

                if state == 5:
                    self._dbg(
                        10,
                        "{}: Setting 'set prompt="
                        "AU_PROMPT'".format(self.hostname)
                    )
                    self.ctrl.sendline('set prompt="{}"'.format("AU_PROMPT"))
                    state = 6
                    timeout = 5
                    continue

                if state == 6:
                    raise ConnectionError("Unable to get shell prompt")

                self._dbg(30, "{}: Connection timed out".format(self.hostname))
                raise ConnectionError("Timeout")

            if event == 12:  # EOF
                if state == 7:
                    self._dbg(
                        10, "{}: First session closed".format(self.hostname)
                    )
                    return False

                raise ConnectionError(
                    "Session closed unexpectedly", self.hostname)

            self._dbg(
                30,
                "{}: Unexpected FSM transition".format(self.hostname)
            )

        else:
            self._dbg(
                50,
                "{}: State machine error. Loop suspected".format(self.hostname)
            )
            return False

        return True

    def disconnect(self):
        self.ctrl.sendcontrol(']')
        self.ctrl.sendline('quit')
