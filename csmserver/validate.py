
from models import logger
from handlers.loader import get_connection_handler_class 
from base import ConnectionContext
from constants import ConnectionType

import socket
import time

def is_connection_valid(platform, urls):
    ctx = ConnectionContext(urls)
    
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
