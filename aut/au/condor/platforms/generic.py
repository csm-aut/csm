# =============================================================================
# generic.py
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
import sys
import logging

import pexpect

from threading import Lock

from ..utils import to_list
from ..exceptions import \
    ConnectionError,\
    ConnectionTimeoutError, \
    CommandSyntaxError, \
    CommandTimeoutError

_PROMPT_IOSXR = re.compile('\w+/\w+/\w+/\w+:.+#')
_PROMPT_SHELL = re.compile('\$\s*|>\s*')

_PROMPT_XML = 'XML> '
_INVALID_INPUT = "Invalid input detected"
_INCOMPLETE_COMMAND = "Incomplete command."
_CONNECTION_CLOSED = "Connection closed"

_PROMPT_IOSXR_RE = re.compile('(\w+/\w+/\w+/\w+:.*?)(\([^()]*\))?#')

_DEVICE_PROMPTS = {
    'Shell': _PROMPT_SHELL,
    'IOSXR': _PROMPT_IOSXR_RE,
}

_logger = logging.getLogger(__name__)


def _c(ctx, msg):
    return "[{}]: {}".format(ctx, msg)


class Connection(object):
    """
    Generic connection driver providing the basic API to the physical devices.
    It implements the following methods:
        - connect
        - disconnect
        - send
        - send_xml

    The Driver class can be extended by the hardware specific classes.
    The derived classes can use different controller implementation
    providing additional flexibility.

    """
    platform = 'Generic'

    def __init__(
            self,
            hostname,
            hosts,
            controller_class,
            account_manager=None,
            debug=5):
        """Initialize the Driver object.

         Args:
            hosts: Single object or list of HopInfo objects
            controller: Controller class used for low level device
                communication.
            account_manager: optional object providing the safe credentials
                management. If password is missing in the HopInfo
                during the connection setup the account_manager is used to
                retrieve the password.
            debug: debug level (0 - none .. 5 - debug)
            logfile: file handler descriptor (fd) for session log file.
        """

        self.hosts = to_list(hosts)
        self.account_manager = account_manager
        self.pending_connection = False
        self.connected = False
        self.command_execution_pending = Lock()
        self.ctrl = None
        self.ctrl_class = controller_class
        self.hostname = hostname
        self.debug = debug
        self.prompt = None
        self.os_type = 'Unknown'

    def __repr__(self):
        name = ""
        for host in self.hosts:
            name += "->{}".format(host)
        return name[2:]

    def connect(self, logfile=None):
        """
        Connection initialization method.
        If logfile is None then the common logfile from
        Args:
            logfile (fd): File description for session log

        Returns:
            True if connection is established successfully
            False on failure.
        """
        if not self.connected:
            self.ctrl = self.ctrl_class(
                self.hostname,
                self.hosts,
                self.account_manager,
                logfile=logfile)

            _logger.info(
                _c(self.hostname, "Connecting to {}".format(self.__repr__())))
            self.connected = self.ctrl.connect()

        if self.connected:
            _logger.info(
                _c(self.hostname, "Connected to {}".format(self.__repr__())))
            self._detect_prompt()
            self.send('terminal exec prompt no-timestamp')
            self.send('terminal len 0')
            self.send('terminal width 0')
        else:
            raise ConnectionError(
                "Connection failed", self.hostname
            )

        return self.connected

    def disconnect(self):
        """
        Tear down the connection

        Args:
            None

        Returns:
            None

        """
        _logger.info(
            _c(self.hostname, "Disconnecting from {}".format(self.__repr__())))
        self.ctrl.disconnect()
        self.connected = False
        self.pending_connection = False
        _logger.info(_c(self.hostname, "Disconnected"))

    def send(self, cmd="", timeout=60, wait_for_string=None):
        """
        Send the command to the device and return the output

        Args:
            cmd (str): command string for execution
            timeout (int): timeout in seconds
            wait_for_string (str): this is optional string that driver
                waits for after command execution. If none the detected
                prompt will be used.

        Returns:
            A string containing the command output.
        """
        if self.connected:
            _logger.debug(
                _c(self.hostname, "Sending command: '{}'".format(cmd)))

            self._execute_command(cmd, timeout, wait_for_string)
            _logger.info(
                _c(self.hostname,
                   "Command executed successfully: '{}'".format(cmd)))
            output = self.ctrl.before
            #if output.startswith(cmd):
                # remove first line which contains the command itself
            #    second_line_index = output.find('\n') + 1
            #    output = output[second_line_index:]
            output = output.replace('\r', '')
            return output

        else:
            raise ConnectionError(
                "Device not connected", host=self.hostname)

    def send_xml(self, command):
        """
        Handle error i.e.
        ERROR: 0x24319600 'XML-TTY' detected the 'informational' condition
        'The XML TTY Agent has not yet been started.
        Check that the configuration 'xml agent tty' has been committed.'
        """
        _logger.debug(_c(self.hostname, "Starting XML TTY Agent"))
        result = self.send("xml", wait_for_string=_PROMPT_XML)
        if result != '':
            return result
        _logger.info(_c(self.hostname, "XML TTY Agent started"))

        result = self.send(command, wait_for_string=_PROMPT_XML)
        self.ctrl.sendcontrol('c')
        self.send()
        return result

    def _detect_prompt(self):
        """
        Detect device prompt.

        :rtype: bool
        :return: True if prompt detected successfully
        """
        if not self.connected:
            raise AssertionError("Session not established")

        prompt = ""
        counter = 0
        max_retry = 8
        # Try couple of iteration
        for retry in xrange(0, max_retry):
            try:
                self.ctrl.sendline()
            except Exception, err:
                _logger.error(_c(
                    self.hostname,
                    "Exception: '{}'".format(err)))
                raise ConnectionError(message=err, host=self.hostname)

            try:
                self.ctrl.expect('\r\n', timeout=10)
            except (pexpect.EOF, pexpect.TIMEOUT):
                _logger.warning(
                    _c(self.hostname,
                       "Failed to get prompt. Retrying ({}/{})".format(
                           retry + 1, max_retry)))
                continue

            if counter % 2:
                _logger.debug(
                    _c(self.hostname,
                       "Detecting prompt ({}/{})".format(
                           retry, max_retry - 1)))

                buf = self.ctrl.before.strip()
                _logger.debug(
                    _c(self.hostname,
                       "Buffer: {}".format(
                           buf)))
                try:
                    last_line = buf.splitlines()[-1]
                except IndexError:
                    _logger.debug(
                        _c(self.hostname,
                            "No response received: '{}'".format(
                                buffer)))
                    continue

                _logger.debug(
                    _c(self.hostname,
                       "Potential prompt: {}".format(
                           last_line)))

                match = False
                for os_type, pattern in _DEVICE_PROMPTS.items():
                    match = re.search(pattern, last_line)
                    if match:
                        prompt = last_line
                        self.os_type = os_type
                        break

                if match:
                    try:
                        self.ctrl.expect_exact(
                            prompt,
                            timeout=1,
                            searchwindowsize=len(prompt)+2
                            )
                    except (pexpect.EOF, pexpect.TIMEOUT):
                        continue
                    break

            counter += 1
        else:
            message = "Device is neither not responding nor not running IOS XR"
            _logger.debug(_c(self.hostname, message))
            self.disconnect()
            raise ConnectionError(message, self.hostname)

        self.prompt = prompt
        _logger.debug(
            _c(self.hostname,
               "{} prompt detected: '{}'".format(self.os_type, self.prompt))
        )
        if self.hostname == None:
            if self.os_type is 'IOSXR':
                # Extract and store hostname from prompt
                match = re.search(r':(.*)#$', prompt)
                if match:
                    name = match.group(1)
                    self.hostname = name

        return True

    def _execute_command(self, cmd, timeout, wait_for_string):
        with self.command_execution_pending:

            try:
                self.ctrl.send(cmd)
                self.ctrl.expect_exact(cmd)
                self.ctrl.send("\n")
                if wait_for_string:
                    _logger.debug(_c(
                        self.hostname,
                        "Waiting for string:'{}'".format(wait_for_string)))
                    self._wait_for_string(wait_for_string, 3, timeout)
                else:
                    self._wait_for_xr_prompt(timeout)

            except CommandSyntaxError, e:
                _logger.error(_c(
                    self.hostname,
                    "Syntax error: '{}'".format(cmd)))
                e.command = cmd
                raise

            except CommandTimeoutError, e:
                _logger.error(_c(
                    self.hostname,
                    "Command timeout: '{}'".format(cmd)))
                e.command = cmd
                raise

            except ConnectionError:
                _logger.error(_c(
                    self.hostname,
                    "Connection Error: '{}'".format(cmd)))
                raise

            except Exception, err:
                _logger.error(_c(
                    self.hostname,
                    "Exception: '{}'".format(err)))
                raise ConnectionError(message=err, host=self.hostname)

    def _wait_for_xr_prompt(self, timeout=60):
        _logger.debug(_c(
                        self.hostname,
                        "Waiting for XR prompt"))
        index = self.ctrl.expect(
                [_PROMPT_IOSXR_RE, _INVALID_INPUT, _INCOMPLETE_COMMAND,
                 pexpect.TIMEOUT, _CONNECTION_CLOSED, pexpect.EOF],
                timeout=timeout
            )
        _logger.debug(_c(self.hostname, "INDEX={}".format(index)))

        if index == 0:
            _logger.debug(_c(self.hostname,
                             "Received XR Prompt: {}".format(
                                 self.ctrl.after)))
            return

        if index == 1:
            _logger.warning(_c(self.hostname, "Invalid input detected"))
            raise CommandSyntaxError(host=self.hostname,
                                     message="Invalid input detected")

        if index == 2:
            _logger.warning(_c(self.hostname, "Incomplete command"))
            raise CommandSyntaxError(host=self.hostname,
                                     message="Incomplete command")

        if index == 3:
            _logger.warning(
                _c(self.hostname, "Timeout waiting for prompt"))
            raise CommandTimeoutError(host=self.hostname,
                                     message="Timeout waiting for prompt")

        if index in [4, 5]:
            raise ConnectionError(
                "Unexpected device disconnect", self.hostname)



    def _wait_for_string(self, expected_string, max_attempts=3, timeout=60):
        index = 0
        state = 0
        attempt = 0
        while attempt < max_attempts + 1:
            index = self.ctrl.expect_exact(
                [expected_string, _INVALID_INPUT, _INCOMPLETE_COMMAND,
                 pexpect.TIMEOUT,
                 _CONNECTION_CLOSED, pexpect.EOF], timeout=timeout,
                #searchwindowsize=len(expected_string)+10
            )
            _logger.debug(_c(self.hostname,
                             "INDEX={}, STATE={}, ATTEMPT={}".format(
                                 index, state, attempt)))
            if index == 0:
                _logger.debug(
                    _c(self.hostname,
                       "Received expected string: {}".format(expected_string)))
                if state == 0:
                    return
                if state == 1:
                    raise CommandSyntaxError(host=self.hostname)

            if index == 1:
                _logger.warning(_c(self.hostname, "Invalid input detected"))

                # command syntax error so wait for prompt again
                state = 1
                continue

            if index == 2:
                _logger.warning(_c(self.hostname, "Incomplete command"))

                # command syntax error so wait for prompt again
                state = 1
                continue

            if index == 3:
                _logger.warning(
                    _c(self.hostname,
                       "Timeout waiting for '{}' ({}/{})".format(
                           expected_string, attempt, max_attempts)))
                # Trying to get prompt again
                self.ctrl.sendline()

            if index in [4, 5]:
                raise ConnectionError(
                    "Unexpected device disconnect", self.hostname)

            attempt += 1
        else:
            _logger.error(_c(self.hostname, "Unexpected response received"))
            if index == 3:
                raise ConnectionTimeoutError(host=self.hostname)
