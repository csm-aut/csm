# =============================================================================
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

import sys

from hopinfo import make_hop_info_from_url
from controllers.pexpect_ctrl import Controller

__all__ = ['make_connection_from_urls','make_connection_from_context',
           'ConnectionAgent']

def make_connection_from_urls(
        name,
        urls,
        platform='generic',
        account_manager=None):

    module_str = 'au.condor.platforms.%s' % (platform)
    try:
        __import__(module_str)
        module = sys.modules[module_str]
        driver_class = getattr(module, 'Connection')
    except ImportError:
        return None

    nodes = []
    for url in urls:
        nodes.append(make_hop_info_from_url(url))

    return driver_class(
        name,
        nodes,
        Controller,
        account_manager=account_manager)


def make_connection_from_context(ctx):
    """This is a driver wrapper handling platforms

    :param ctx: A context object
    :returns: driver class
    """

    module_str = 'au.condor.platforms.%s' % (ctx.host.platform)
    __import__(module_str)
    module = sys.modules[module_str]

    driver_class = getattr(module, 'Connection')
    nodes = []
    for url in ctx.host.urls:
        nodes.append(make_hop_info_from_url(url))

    return driver_class(
        ctx.host.hostname,
        nodes,
        Controller)


class ConnectionAgent():
    def __init__(self, obj, session_log_path=None, mode='a+'):
        self.obj = obj
        self.session_log_path = session_log_path
        self.mode = mode
        self.logfile = None

    def __enter__(self):
        if self.session_log_path:
            try:
                self.logfile = open(self.session_log_path, self.mode)
            except IOError:
                raise

        self.obj.connect(logfile=self.logfile)
        return self.obj

    def __exit__(self, type, value, traceback):
        self.obj.disconnect()
        if self.logfile:
            self.logfile.close()


def Connection(hostname, urls, account_manager=None, debug=0):
        return make_connection_from_urls(
            hostname, urls, account_manager=account_manager)
