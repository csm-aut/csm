# =============================================================================
# ssh
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

_logger = logging.getLogger(__name__)

MODULUS_TOO_SMALL = "modulus too small"
PROTOCOL_DIFFER = "Protocol major versions differ"
NEWSSHKEY = "fingerprint is"
KNOWN_HOSTS = "added.*to the list of known hosts"
HOST_KEY_FAILED = "key verification failed"
COULD_NOT_RESOLVE = "Could not resolve hostname"


class SSH(Protocol):
    def __init__(self, controller, device, account_manager, logfile):
        super(SSH, self).__init__(controller, device, account_manager, logfile)

        command = self._get_command()
        self._spawn_session(command)

    def _get_command(self, version=2):
        if self.username:
            command = "ssh -{} -p {} {}@{}".format(
                version, self.port, self.username, self.hostname
            )
        else:
            command = "ssh -{} -p {} {}".format(
                version, self.port, self.hostname
            )
        return command

    def connect(self):
        state = 0
        transition = 0
        event = 0
        failed = False
        max_transitions = 10
        timeout = 180  # TIME FOR SSH CONNECTION BEFORE ERROR
        ssh_version = 2

        while not failed and transition < max_transitions + 1:
            transition += 1
            event = self.ctrl.expect(
                [PASS, XR_PROMPT, SHELL_PROMPT, NEWSSHKEY,
                 KNOWN_HOSTS, HOST_KEY_FAILED, CONNECTION_REFUSED,
                 RESET_BY_PEER, PERMISSION_DENIED, MODULUS_TOO_SMALL,
                 PROTOCOL_DIFFER, UNABLE_TO_CONNECT,
                 pexpect.TIMEOUT, pexpect.EOF],
                timeout=timeout, searchwindowsize=120
            )
            self._dbg(10, "{}: EVENT={}, STATE={}, TRANSITION={}".format(
                self.hostname, event, state, transition
            ))
            timeout = 60
            if event == 0:  # PASS
                if state in [0, 4]:
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

                    state = 1
                    timeout = 30
                    continue

                if state == 1:
                    self._dbg(
                        10, "{}: Authentication error".format(
                            self.hostname)
                    )
                    self.disconnect()
                    raise ConnectionAuthenticationError(
                        "Authentication error", self.hostname)

            if event == 1:  # XR_PROMPT
                if state in [0, 1]:
                    self._dbg(10, "{}: Received IOS XR prompt".format(
                        self.hostname
                    ))
                    break
                if state == 5:
                    self._dbg(
                        10,
                        "{}: Received XR prompt after "
                        "connection failure".format(self.hostname)
                    )
                    return False

            if event == 2:  # SHELL_PROMPT
                if state in [0, 1, 2, 3]:
                    self._dbg(10, "{}: Received shell prompt.".format(
                        self.hostname)
                    )
                    break  # successfully got prompt
                if state == 5:
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

            if event == 3:  # NEWSSHKEY
                if state == 0:
                    self._dbg(
                        10, "{}: Confirming new key".format(
                            self.hostname)
                    )
                    self.ctrl.sendline("yes")
                    state = 4
                    timeout = 10
                continue

            if event == 4:  # KNOWN_HOSTS
                if state == 4:
                    self._dbg(
                        10, "{}: Key added to known hosts".format(
                            self.hostname)
                    )
                    state = 0
                continue

            if event == 5:  # HOST_KEY_FAILED
                if state == 0:
                    self._dbg(
                        30,
                        "{}: Remote host identification has "
                        "changed".format(self.hostname)
                    )
                    raise ConnectionError(
                        "Remote host identification has "
                        "changed", self.hostname)

            if event == 6:  # CONNECTION REFUSED
                self._dbg(
                    30,
                    "{}: Connection refused".format(self.hostname)
                )
                raise ConnectionError("Connection refused", self.hostname)

            if event == 7:  # RESET_BY_PEER
                self._dbg(
                    30,
                    "{}: Reset by peer".format(self.hostname)
                )
                raise ConnectionError(
                    "Connection reset by peer", self.hostname)

            if event == 8:  # PERMISSION_DENIED
                self._dbg(
                    30,
                    "{}: Permission denied.".format(self.hostname)
                )
                raise ConnectionAuthenticationError(
                    "Permission denied", self.hostname)

            if event == 9:  # MODULUS_TOO_SMALL
                if state == 0:

                    self._dbg(10, "{}: Fallback to SSH v1".format(
                        self.hostname)
                    )
                    command = self._get_command(version=1)
                    self._spawn_session(command)
                    continue

            if event == 10:  # PROTOCOL_DIFFER
                if state == 0:
                    if ssh_version == 2:
                        self._dbg(10, "{}: Protocol version differs".format(
                            self.hostname)
                        )
                        command = self._get_command(version=1)
                        self._spawn_session(command)
                        ssh_version = 1
                        continue
                    else:
                        self._dbg(
                            40,
                            "{}: Can't connect neither v1 nor v2".format(
                                self.hostname)
                        )
                        raise ConnectionError(
                            "Protocol version differs", host=self.hostname
                        )

            if event == 11:  # UNABLE_TO_CONNECT
                if state == 0:
                    self._dbg(30, "{}: Unable to connect".format(self.hostname))
                    timeout = 10
                    state = 5
                    continue

            if event == 12:  # TIMEOUT
                if state == 0:
                    self._dbg(
                        40,
                        "{}: Timeout getting connection".format(self.hostname)
                    )
                    raise ConnectionError(
                        "Timeout getting connection", self.hostname)

                if state == 1:
                    self._dbg(
                        10,
                        "{}: Setting 'PS1=AU_PROMPT'".format(self.hostname)
                    )
                    self.ctrl.sendline('PS1="{}"'.format("AU_PROMPT"))
                    state = 2
                    timeout = 10
                    continue

                if state == 2:
                    self._dbg(
                        10,
                        "{}: Setting 'set prompt="
                        "AU_PROMPT'".format(self.hostname)
                    )
                    self.ctrl.sendline('set prompt="{}"'.format("AU_PROMPT"))
                    state = 3
                    timeout = 10
                    continue

                if state == 3:
                    raise ConnectionError(
                        "Unable to get the prompt", self.hostname)

                self._dbg(10, "{}: Timeout".format(
                    self.hostname)
                )
                raise ConnectionError("Timeout")

            if event == 13:  # EOF
                if state == 5:
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
        self.ctrl.sendline('\x03')
