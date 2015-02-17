# ==============================================================================
# cast.py -Utility module providing simple casting functions
#
# Copyright (c)  2014, Cisco Systems
# All rights reserved.
#
# Author: Klaudiusz Staniek
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
# ==============================================================================


def to_list(item):
    """
    If the given item is iterable, this function returns the given item.
    If the item is not iterable, this function returns a list with only the
    item in it.

    @type  item: object
    @param item: Any object.
    @rtype:  list
    @return: A list with the item in it.
    """
    if hasattr(item, '__iter__'):
        return item
    return [item]


def to_device(device, default_protocol='telnet', default_domain=''):
    """
    Given a string or a Host object, this function returns a Host object.

    @type  host: string|Host
    @param host: A hostname (may be URL formatted) or a Host object.
    @type  default_protocol: str
    @param default_protocol: Passed to the Host constructor.
    @type  default_domain: str
    @param default_domain: Appended to each hostname that has no domain.
    @rtype:  Host
    @return: The Host object.
    """
    if device is None:
        raise TypeError('None can not be cast to Device')
    if hasattr(device, 'get_address'):
        return device
    if default_domain and '.' not in device:
        device += '.' + default_domain
    #return Exscript.Host(device, default_protocol=default_protocol)
