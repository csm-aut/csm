# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
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
from models import logger
from handlers.loader import get_connection_handler_class 
from base import ConnectionContext
from constants import ConnectionType

import socket
import time

def is_connection_valid(db_session, platform, urls):
    ctx = ConnectionContext(db_session, urls)
    
    try:
        handler_class = get_connection_handler_class(platform)
        if handler_class is None:
            logger.error('Unable to get connection handler for %s', platform)
            
        handler = handler_class()
        handler.execute(ctx)
    except:
        logger.exception('is_connection_valid hit exception')
    
    return ctx.success

"""
This function check reachability for specified hostname/port
It tries to open TCP socket.
It supports IPv6.
:param host string: hostname or ip address string
:rtype: str
:param port number: tcp port number
:rtype: bool
:return: True if host is reachable else false
"""
def is_reachable(host, port=23):
    try:
        addresses = socket.getaddrinfo(
            host, port, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
    except socket.gaierror:
        return False

    for family, socktype, proto, cannonname, sockaddr in addresses:
        sock = socket.socket(family, socket.SOCK_STREAM)
        #sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        sock.settimeout(5)
        try:
            sock.connect(sockaddr)
        except IOError as e:
            continue

        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        # Wait 2 sec for socket to shutdown
        time.sleep(2)
        break
    else:
        return False
    return True
