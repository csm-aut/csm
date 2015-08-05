# =============================================================================
# device.py - Define Device class providing basic device functions
#
# Copyright (c)  2014, Cisco Systems
# All rights reserved.
#
# Author: Suryakant Kewat
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

from utils.network import is_reachable, protocol2port_map
from utils.event import Event
from utils.cast import to_list

from packages import DevicePackages

from threading import Lock

from urlparse import urlparse
from contextlib import contextmanager

import logging
import pexpect
import re
import time
import os
import sys
import datetime
import getpass
import condor


# Error codes
DEVICE_OK = 0
DEVICE_NOT_REACHABLE = 1
DEVICE_AUTH_FAILURE = 2
DEVICE_TIMEOUT = 3


_logger = logging.getLogger(__name__)


class DeviceError(Exception):
    pass


class NodeInfo(object):

    """
    NodeInfo class contains all the information needed
    for device access.
    It is initiated by passing device URL.
    Optionally there could be a callable passed for
    reachability verification.
    """

    def __init__(self, url, verify_reachability=None):
        parsed = urlparse(url)
        self.url = url
        self.hostname = parsed.hostname
        self.username = parsed.username
        self.password = parsed.password
        self.scheme = parsed.scheme
        self.port = parsed.port
        self.node_name = self.get_node_name()
        self.port = parsed.port if parsed.port else \
            protocol2port_map.get(self.scheme, None)

        self.verify_reachability = verify_reachability
        if not self.password:
            self.password = self._get_password("%s:%s@%s Password:" %
                                               (self.scheme, self.username, self.hostname))

    def is_valid(self):
        if self.scheme not in ['telnet', 'ssh']:
            return False
        return True

    def is_reachable(self):
        if self.verify_reachability and \
                hasattr(self.verify_reachability, '__call__'):
            return self.verify_reachability(host=self.hostname, port=self.port)
        # return true if can't verify
        return True

    def get_node_name(self):
        name = self.hostname.split("/")[-1]
        if self.port:
            return "{}:{}".format(name, self.port)
        else:
            return name

    def _get_password(self, msg):
        dev_password = getpass.getpass("\n" + msg)
        if not dev_password:
            dev_password = getpass.getpass(msg)
        return dev_password

    def __repr__(self):
        return "{}://{}:{}".format(self.scheme, self.hostname, self.port)


class Device(object):

    def __init__(
            self,
            url_chain,
            name=None,
            debug=0,
            stdout=None,
            stderr=None,
            session_log=None,
            log=None
    ):
        # Event emitted when new command output received
        self.command_output_received = Event()
        # Event emitted when device changed the name
        self.name_changed = Event()
        # Event emitted when device wants to log the message
        self.log_event = Event()
        self.log_event.listen(self._log)

        self.node_chain = []
        self.stdby_nodes = []
        self.debug = debug
        self.url_chain = url_chain

        print "url_chain = " +str(url_chain)

        for url in iter(to_list(url_chain)):
            if "," in url:
                # It has standby
                alt_address = url.split(',')
                if ('.' in alt_address[-1]):
                    #Alternate mgmt IP given for standby connections
                    for alt_ip in alt_address[1:] :
                        self.stdby_nodes.append('@'.join(url.split("@")[:-1]) + "@" + alt_ip)
                else :
                    #Alternate ports given for standby connections
                    for alt_port in alt_address[1:] :
                        self.stdby_nodes.append(':'.join(url.split(":")[:-1]) + ":" + alt_port)
                url = url.split(",")[0]

            node_info = NodeInfo(url)
            if not node_info.is_valid():
                self._dbg(
                    2, "For {} protocol {} is not supported or "
                    "{} is invalid URL".format(
                        node_info.hostname,
                        node_info.scheme,
                        node_info.url)
                )
                continue
            self.node_chain.append(node_info)

        if "," in self.url_chain[-1] :
            self.url_chain[-1] = self.url_chain[-1].split(",")[0]
        if self.node_chain:
            self.node_chain[0].verify_reachability = is_reachable

        self.session = None
        self.session_log = session_log
        self.connected = False
        self.last_command_succeed = False

        self.pending_connection = False
        self.command_execution_pending = Lock()
        self.connecting_lock = Lock()

        self.output_store_dir = "."

        if name:
            self.name = name
            #self.name = self.node_chain[-1].node_name
        else:
            self.name = self.node_chain[-1].node_name \
                if self.node_chain else "Unknown"

        if stdout is None:
            self.stdout = open(os.devnull, 'w')
        else:
            self.stdout = stdout

        if stderr is None:
            self.stderr = sys.stderr
        else:
            self.stderr = stderr

        self.info = {}

        self.packages = DevicePackages()

        self.log_event.disconnect(self._log)

        self.error_code = None

    def store_property(self, key, value):
        self._dbg(4, "Store '{}' <- '{}'".format(key, value))
        self.info[key] = value

    def get_property(self, key):
        return self.info.get(key, None)

    def __repr__(self):
        name = ""
        for node in self.node_chain:
            name += "->{}".format(node)
        return name[2:]

    def execute_command(self,command,timeout=60):
        return self.session.connected, self.session.send(command,timeout)

    def disconnect(self):
        return self.session.disconnect()

    def connect(self):
        status = False
        self.session = condor.make_connection_from_urls( "None", self.url_chain)
        try :
            print "Connecting to device"
            status = self.session.connect(self.session_log)
        except Exception as e:
            print "Failed to connect device"
            print e

        if not status and self.stdby_nodes :
            for node in self.stdby_nodes :
                new_url_chain = self.url_chain
                new_url_chain[-1] = node
                print "Trying to connect to: ", new_url_chain[-1]
                self.session = condor.make_connection_from_urls( "None", new_url_chain)
                try :
                    status = self.session.connect(self.session_log)
                except :
                    print "Failed to connect to : ",node
        return status

    def reconnect(self):
        """
         Wait for system to come up with max timeout as 10 Minutes
        changed timeout from 900 to 1800 for the migration to eXR purpose
        """
        status = False
        timeout = 1800
        poll_time = 30
        time_waited = 0
        print "System going for reload., please wait!!"
        time.sleep(60)
        self.session.disconnect()


        try :
            self.session.connect(self.session_log)
        except :
            pass 

        while 1:
            time_waited += poll_time
            if time_waited >= timeout:
                break
            else:
                time.sleep(poll_time)
                print "\nRetry count :%s @ %s"%(time_waited/poll_time,time.strftime("%H:%M:%S", time.localtime()))
                try:
                    status = self.session.connect(self.session_log)
                except:
                    continue

                if status :
                    return True
        return status

    def _dbg(self, level, msg):
        if self.debug <= level:
            return
        self.stderr.write("{} [{}]: {}\n".format(
            datetime.datetime.now(), self.name, msg)
        )

    def _log(self, msg):
        message = "{}: {}".format(self.name, msg)
        self._dbg(4, msg)
        self.stdout.write(message + '\n')

    def log(self, msg):
        self.log_event(msg)


# for tests use the file device.txt in format:
# ssh://user:pass@localhost ssh://user:pass@localhost
# ssh://user:pass@localhost ssh://user:pass@localhost telnet://cisco:cisco@172.28.98.6:23
# ssh://user:wrong@localhost ssh://user:wrong@localhost telnet://cisco:cisco1@172.28.98.6:23
# ssh://user:wrong@localhost ssh://user:pass@localhost telnet://cisco:cisco@172.28.98.6:23
# ssh://user:pass@localhost ssh://user:wrong@localhost telnet://cisco:cisco@172.28.98.6:23
# ssh://user:wrong@localhost ssh://user:wrong@localhost telnet://cisco:cisco@172.28.98.6:23
# telnet://cisco:cisco@172.28.98.6:23 http://www.cisco.com
# telnet://cisco:cisco@bdlk1-b05-ts-01:2033
