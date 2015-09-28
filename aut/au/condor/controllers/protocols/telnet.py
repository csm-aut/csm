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




    def connect(self, connect_with_reconfiguration=False):

        if connect_with_reconfiguration:
            print("We are using the special telnet connect tunnel")
        state = 0
        transition = 0
        event = 0
        failed = False
        max_transitions = 10
        timeout = 300  # TIME FOR TELNET CONNECTION BEFORE ERROR

        while not failed and transition < max_transitions + 1:
            transition += 1

            event = self.ctrl.expect(
                [ESCAPE_CHAR, PASSWORD_OK, RECONFIGURE_USERNAME_PROMPT, SET_USERNAME, SET_PASSWORD, USERNAME, PASS,
                 XR_PROMPT, SHELL_PROMPT, PRESS_RETURN, UNABLE_TO_CONNECT,
                 CONNECTION_REFUSED, RESET_BY_PEER, PERMISSION_DENIED,
                 AUTH_FAILED, pexpect.TIMEOUT, pexpect.EOF],
                timeout=timeout, searchwindowsize=80
            )
            try:
                print "transition " + str(transition) + " event =  " + str(event)
                print "transition " + str(transition) + " state =  " + str(state)

                print "transition " + str(transition) + " ctrl.before" + self.ctrl.before
                print(type(self.ctrl.after).__name__)
                print "transition " + str(transition) + " ctrl.after" + self.ctrl.after
            except Exception as inst:
                print("Oops here is an error occurred~~~~")

                print(type(inst))
                print(inst.args)
                print(inst)

            self._dbg(10, "{}: EVENT={}, STATE={}, TRANSITION={}".format(
                self.hostname, event, state, transition
            ))
            timeout = 60
            #print "event = " + str(event)
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
                    print("event 0 ConnectionError Unexpected session init ")
                    raise ConnectionError("Unexpected session init")

            if event == 1:  # PASSWORD_OK
                if state in [0, 1]:
                    self._dbg(
                        30,
                        "{}: Terminal server press "
                        "return ".format(self.hostname)
                    )
                    self.ctrl.send('\r\n')
                    timeout = 10
                    continue

            if event == 2:  # RECONFIGURE_USERNAME_PROMPT
                state = 1
                timeout = 300
                self._dbg(
                    10,
                    "{}: Waiting {} sec for entering username prompt".format(
                        self.hostname, timeout)
                )
                continue


            if event == 3: # SET_USERNAME
                print "setting username"
                if state in [0, 1, 2]:

                    index = 2
                    while index == 2:

                        index = self.ctrl.expect(
                            [pexpect.TIMEOUT, pexpect.EOF, SET_USERNAME],
                            timeout=5
                        )
                        if index == 0:
                            print("inside event 3 - index expected = TIMEOUT")
                        if index == 1:
                            print("inside event 3 - index expected = EOF")

                        if index == 2:  # console connected through TS
                            print("inside event 3 - index expected = SET_USERNAME")

                    print "setting username = " + self.username
                    self._dbg(
                        10,
                        "{}: Sending username: '{}'".format(
                            self.hostname, self.username)
                    )

                    self.ctrl.sendline(self.username)
                    state = 0
                    timeout = 10
                    continue
                else:
                    print("calling self.disconnect from telnet.py - SET_USERNAME state != 0, 1, or 2")
                    self.disconnect()
                    print("event 2 ConnectionAuthenticationError(host=self.hostname) ")
                    raise ConnectionAuthenticationError(host=self.hostname)



            if event == 4:  #SET_PASSWORD
                if state in [0, 1]:  # if waiting for pass send pass

                    index = 2
                    while index == 2:

                        index = self.ctrl.expect(
                            [pexpect.TIMEOUT, pexpect.EOF, SET_PASSWORD],
                            timeout=5
                        )
                        if index == 0:
                            print("inside event 4 - index expected = TIMEOUT")
                        if index == 1:
                            print("inside event 4 - index expected = EOF")

                        if index == 2:  # console connected through TS
                            print("inside event 4 - index expected = SET_PASSWORD")

                    password = self._acquire_password()
                    if password:
                        self._dbg(
                            10,
                            "{}: Sending password: {}".format(self.hostname, password)
                        )

                        print "setting password  = " + password


                        self.ctrl.sendline(password)
                        state += 1
                        timeout = 10

                        continue

                    else:
                        print("calling self.disconnect from telnet.py - SET_PASSWORD _acquire_password returns null")
                        self.disconnect()
                        print("event 3 ConnectionAuthenticationError(Password not provided, self.hostname) ")
                        raise ConnectionAuthenticationError("Password not provided", self.hostname)



                    # state = 1 -> move to wait for password confirmation - will enter password a second time
                    # state = 0 -> just configured username, need to configure password again twice
                else:
                    print("calling self.disconnect from telnet.py - SET_PASSWORD state != 0 or 1")
                    self.disconnect()
                    print("event 3 ConnectionAuthenticationError(host=self.hostname)")
                    raise ConnectionAuthenticationError(host=self.hostname)



            if event == 5:  # USERNAME
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
                    print("calling self.disconnect from telnet.py - USERNAME state =4")
                    self.disconnect()
                    print("event 4 ConnectionAuthenticationError(host=self.hostname)")
                    raise ConnectionAuthenticationError(host=self.hostname)

            if event == 6:  # PASS
                if state in [1, 2, 3]:  # if waiting for pass send pass
                    password = self._acquire_password()
                    if password:
                        self._dbg(
                            10,
                            "{}: Sending password: '***'".format(self.hostname)
                        )
                        self.ctrl.sendline(password)
                    else:
                        print("calling self.disconnect from telnet.py - PASS _acquire_password returns null")
                        self.disconnect()
                        print("event 5 ConnectionAuthenticationError")
                        raise ConnectionAuthenticationError(
                            "Password not provided", self.hostname)

                    state = 4  # move to wait for prompt
                    timeout = 30
                continue

            if event == 7:  # XR PROMPT
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

            if event == 8:  # SHELL PROMPT
                if state in [4, 5, 6]:
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

            if event == 9:  # PRESS_RETURN
                if state in [0, 1, 2]:
                    self._dbg(
                        30,
                        "{}: Terminal server press "
                        "return ".format(self.hostname)
                    )
                    self.ctrl.send('\r\n')
                    continue


            if event == 10:  # UNABLE_TO_CONNECT
                if state == 0:
                    self._dbg(30, "{}: Unable to connect".format(self.hostname))
                    state = 7
                    timeout = 10
                    continue

            if event == 11:  # CONNECTION REFUSED
                print("event 10 ConnectionError")
                raise ConnectionError("Connection refused", self.hostname)

            if event == 12:  # RESET_BY_PEER
                print("event 11 ConnectionError")
                raise ConnectionError(
                    "Connection reset by peer", self.hostname)

            if event == 13:  # PERMISSION_DENIED
                self._dbg(
                    30,
                    "{}: Permission denied.".format(self.hostname)
                )
                print("event 12 ConnectionAuthenticationError")
                raise ConnectionAuthenticationError(
                    "Permission denied", self.hostname)

            if event == 14:  # AUTH_FAILED
                if state == 4:
                    print("calling self.disconnect from telnet.py - AUTH_FAILED state = 4")
                    self.disconnect()
                    print("event 13 ConnectionAuthenticationError")
                    raise ConnectionAuthenticationError(
                        "Authentication failed", self.hostname)

            if event == 15:  # TIMEOUT
                if connect_with_reconfiguration:

                    if state == 1:
                        self._dbg(
                            30,
                            "{}: Connection timed out waiting for "
                            "initial response".format(self.hostname)
                        )
                        self._dbg(30, "{}: Sending CR/LF".format(self.hostname))
                        state = 2
                        timeout = 20
                        continue



                    self._dbg(
                        20,
                        "{}: Timeout "
                        "received ".format(self.hostname)
                    )

                    self.disconnect()
                    print("event 15 ConnectionError(Timeout)")
                    raise ConnectionError("Timeout")

                else:
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

                    if state == 2:
                        state = 4
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
                        print("event 14 ConnectionError Unable to get shell prompt")
                        raise ConnectionError("Unable to get shell prompt")

                    self._dbg(30, "{}: Connection timed out".format(self.hostname))
                    print("event 14 ConnectionError Timeout")
                    raise ConnectionError("Timeout")

            if event == 16:  # EOF
                if state == 7:
                    self._dbg(
                        10, "{}: First session closed".format(self.hostname)
                    )
                    return False
                print("event 15 ConnectionError")
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