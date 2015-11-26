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


from au.lib.global_constants import *
from au.plugins.plugin import IPlugin

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

    def start(self, device, *args, **kwargs):

        repo = kwargs.get('repository', None)
        if not repo :
            return True
        parsed = urlparse(repo)
        hostname = parsed.hostname
        if not hostname:
            self.warning('Invalid repository url {}'.format(repo))

        if parsed.scheme not in ['tftp', 'sftp', 'ftp']:
            self.warning('Protocol not supported to reach repository: {}'.format(
                parsed.scheme
            ))

        if parsed.netloc.find(';') != -1:
            hostname, vrf_name = parsed.netloc.split(';')
            if hostname.find(':') != -1:
                hostname = hostname.split(':')[0]
            cmd = 'ping vrf {} {}'.format(vrf_name, hostname)
        else:
            cmd = 'ping {}'.format(hostname)

        success, output = device.execute_command(cmd)
        if success:
            if output.find("Success rate is 100 percent") != -1:
                return True
            if output.find("Success rate is 0") != -1:
                self.warning("Repository host is not responding")
            if output.find("UUUUU") != -1:
                self.warning("Repository host is not reachable")
            if output.find("Invalid vrf table name"):
                self.warning("Wrong management vrf name or vrf not configured")
            if output.find("Bad hostname or protocol not running") != -1:
                self.warning("Bad hostname or protocol not running")
        else:
            self.warning("Ping command execution timeout/failed")
        return True

        host = kwargs['session']
        pkg_path = kwargs['repository']
        if not pkg_path:
            self.error(
                "Couldn't ping, package repository path is not provided")
            return -1
        try:
            host.expect_exact("#", timeout=30)
        except:
            pass
        pat = re.compile('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
        ipaddr = re.findall(pat, pkg_path)
        protocol = ['tftp:', 'sftp:', 'ftp:']
        path_list = pkg_path.split('/')
        if not len(ipaddr):
            self.error("Invalid TFTP address ")
            return -1

        if len(path_list[0]) if path_list[0] else path_list[1] in protocol:
            cmd = "ping " + ipaddr[0]
            self.info(cmd)
            host.sendline(cmd)
            try:
                host.expect_exact(
                    [INVALID_INPUT, MORE, "#", PROMPT, EOF], timeout=tout_cmd
                )
            except:
                self.warning("Command: Timed out, before considering"
                              " this as failure. Please check console log file for details")
                return 0

        out = host.before
        if (out.find('Success rate is 0') != -1 or
                out.find('Bad hostname or protocol not running') != -1 or
                out.find('UUUUU') != -1):
            self.warning(
                "TFTP server %s is not reachable from device" % ipaddr)
            return -1
        return 0
