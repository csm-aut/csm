# ==============================================================================
# file
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

import codecs

from au.device import Device

from urlparse import urlparse


def get_devices_from_txt(filename, remove_duplicates=True, encoding='utf-8'):

    devices = []
    have = set()
    try:
        with codecs.open(filename, 'r', encoding) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                urls = line.split(' ')
                # parse the last url
                hostname = urlparse(urls[-1]).hostname
                if remove_duplicates and hostname in have:
                    continue

                have.add(hostname)
                devices.append(Device(urls))

    except IOError:
        raise IOError('No such file: %s' % filename)

    return devices

def get_urls_from_txt(filename, remove_duplicates=True, encoding='utf-8'):

    devices = []
    have = set()
    try:
        with codecs.open(filename, 'r', encoding) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                urls = line.split(' ')
                # parse the last url
                hostname = urlparse(urls[-1]).hostname
                if remove_duplicates and hostname in have:
                    continue

                have.add(hostname)
                devices.extend(urls)

    except IOError:
        raise IOError('No such file: %s' % filename)

    return devices
