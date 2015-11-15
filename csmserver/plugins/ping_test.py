#==============================================================================
# ping_test.py - Plugin for checking reachability to tftp.
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


#from au.lib.global_constants import *
from plugin import IPlugin

from urlparse import urlparse


class PingTestPlugin(IPlugin):

    """
    A plugin to check reachability of tftp
    or repository IP address given

    """
    NAME = "PING_TEST"
    DESCRIPTION = "Repository Reachability Check"
    TYPE = "PRE_UPGRADE"
    VERSION = "0.0.1"

    @staticmethod
    def start(manager, device, *args, **kwargs):
        ctx = device.get_property("ctx")

        try:
            server_repository_url = ctx.server_repository_url
        except AttributeError:
            manager.error("No repository path provided")

        if server_repository_url is None:
            manager.log("Skipping, repository not provided")
            return

        parsed = urlparse(server_repository_url)
        hostname = parsed.hostname
        if not hostname:
            manager.warning('Invalid repository url {}'.format(server_repository_url))

        if parsed.scheme not in ['tftp', 'sftp', 'ftp']:
            manager.error('Protocol not supported to reach repository: {}'.format(
                parsed.scheme
            ))

        if parsed.netloc.find(';') != -1:
            hostname, vrf_name = parsed.netloc.split(';')
            if hostname.find(':') != -1:
                hostname = hostname.split(':')[0]
            cmd = 'ping vrf {} {}'.format(vrf_name, hostname)
        else:
            cmd = 'ping {}'.format(hostname)

        output = device.send(cmd)
        if output.find("Success rate is 100 percent") != -1:
            manager.log("Repository is reachable.")
            return True

        if output.find("Success rate is 0") != -1:
            manager.error("Repository host is not responding")
        if output.find("UUUUU") != -1:
            manager.error("Repository host is not reachable")
        if output.find("Invalid vrf table name"):
            manager.error("Wrong management vrf name or vrf not configured")
        if output.find("Bad hostname or protocol not running") != -1:
            manager.error("Bad hostname or protocol not running")

        manager.error("Unknown error")
        return False