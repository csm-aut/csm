# =============================================================================
# HopInfo
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

from urlparse import urlparse

from exceptions import InvalidHopInfoError

# Standard protocol to port mapping
protocol2port_map = {
    'telnet': 23,
    'ssh': 22,
}


def make_hop_info_from_url(url, verify_reachability=None):
    """
    This is a factory function to build HopInfo object from url.
    It allows only telnet and ssh as a valid protocols.

    Args:
        url (str): The url string describing the node. i.e.
            telnet://username@1.1.1.1. The protocol, username and address
            portion of url is mandatory. Port and password is optional.
            If port is missing the standard protocol -> port mapping is done.
            The password is optional i.e. for TS access directly to console
            ports.

        verify_reachability: This is optional callable returning boolean
            if node is reachable. It can be used to verify reachability
            of the node before making a connection. It can speedup the
            connection process when node not reachable especially with
            telnet having long timeout.

    Returns:
        HopInfo object or None if url is invalid or protocol not supported

    """
    parsed = urlparse(url)
    hop_info = HopInfo(
        parsed.scheme,
        parsed.hostname,
        parsed.username,
        parsed.password,
        parsed.port,
        verify_reachability=verify_reachability
    )
    if hop_info.is_valid():
        return hop_info
    raise InvalidHopInfoError


class HopInfo(object):
    """
    HopInfo class contains all the information needed
    for node (jump host or device) access.
    """
    def __init__(
            self,
            protocol,
            hostname,
            username,
            password=None,
            port=None,
            verify_reachability=None):
        """
        Initialize the HopInfo with the provided arguments:

        Args:
            protocol (str): 'telnet' or 'ssh'. The other protocols are not
                implemented.
            hostname (str): The hostname or IP address of the node
            username (str): The username for node access
            password (str): The password for provided username. This
                argument is optional and can be omitted. i.e. ssh hey auth
                or TS without authentication.
            port (number): Optional TCP port number. If not provided the
                the standard mapping for telnet and ssh is done automatically.
            verify_reachability (callable): This is optional callable returning
                True if if node is reachable. It can be used to verify
                reachability of the node before making a connection.
                It can speedup the connection process when node not
                reachable especially with telnet having long timeout.
        """

        self.hostname = hostname
        self.username = username
        self.password = password
        self.protocol = protocol

        # if port not provided map port based on protocol standards
        self.port = port if port else \
            protocol2port_map.get(self.protocol, None)

        self.verify_reachability = verify_reachability

    def is_valid(self):
        if self.protocol not in ['telnet', 'ssh']:
            return False
        if self.username is None:
            return False
        return True

    def is_reachable(self):
        if self.verify_reachability and \
                hasattr(self.verify_reachability, '__call__'):
            return self.verify_reachability(host=self.hostname, port=self.port)
        # assume is reachable if can't verify
        return True

    def __repr__(self):
        return "{}://{}@{}:{}".format(
            self.protocol,
            self.username,
            self.hostname,
            self.port)
