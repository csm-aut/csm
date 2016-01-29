# =============================================================================
# packages.py
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
# =============================================================================


import re
from itertools import imap, repeat
from collections import defaultdict
import copy


platforms = 'asr9k|hfr'

pkg_1_re = re.compile(r'(?P<disk>\w+):'
                      r'(?P<platform>' + platforms + ')-'
                      r'(?P<sub_pkg_name>\w+)-'
                      r'(?P<pkg_name>\w+)-'
                      r'(?P<architecture>p\w+)-'
                      r'(?P<version>\d+\.\d+\.\d+)')

pkg_2_re = re.compile(r'(?P<disk>\w+):'
                      r'(?P<platform>' + platforms + ')-'
                      r'(?P<pkg_name>\w+)-'
                      r'(?P<architecture>p\w+)-'
                      r'(?P<version>\d+\.\d+\.\d+)')


smu_1_re = re.compile(r'(?P<disk>\w+):'
                      r'(?P<platform>' + platforms + ')-'
                      r'(?P<architecture>p\w+)-'
                      r'(?P<version>\d+\.\d+\.\d+)\.'
                      r'(?P<pkg_name>\w+)-'
                      r'(?P<sub_version>\d+\.\d+\.\d+)')


packages_re = [pkg_1_re, pkg_2_re, smu_1_re]


def get_packages_from_show_install(output):
    packages = set()
    lines = output.split('\n')
    start = False
    for line in iter(lines):

        if "Active Packages:" in line:
            start = True
            continue
        if start:
            filename = line.strip()
            if filename == "":
                break

            packages.add(PackageInfo(filename))
    return packages


class PackageInfo(object):

    def __init__(self, filename):

        self._info = defaultdict(repeat("N/A").next)
        self._filename = filename
        self._filename_updated()

    def _filename_updated(self):
        # can't use iter with sentil
        for found in imap(
                lambda pattern: re.search(pattern, self._filename),
                packages_re):
            if found:
                break
        else:
            self.is_valid = False
            return

        self._info = defaultdict(repeat("N/A").next, found.groupdict())
        self._info['smu'] = True if self.pkg_name.startswith("CSC") else False
        self.is_valid = True

    def __repr__(self):
        return self._filename

    def __hash__(self):
        return hash(self._filename)

    def __getattr__(self, item):
        return self.__dict__['_info'][item]

    def __setattr__(self, key, value):
        info = self.__dict__.get('_info', None)
        if info:
            if key in info.keys():
                return
        else:
            super(PackageInfo, self).__setattr__(key, value)

    def __cmp__(self, other):
        return cmp(self._filename, other._filename)

    def __copy__(self):
        return PackageInfo(self._filename)

    def __deepcopy__(self, memo):
        return PackageInfo(copy.deepcopy(self._filename, memo))

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, value):
        self._filename = value
        self._update_filename(value)


class DevicePackages(object):

    def __init__(self):

        self.active = defaultdict(set)
        self.inactive = defaultdict(set)
        self.committed = defaultdict(set)
        self.superceded = defaultdict(set)

    def init_from_show_install(self, output):
        lines = output.split('\n')
        start = False
        find_node = False
        node = None
        node_re = re.compile(r'Node (?P<node>\w+/\w+/\w+) ')
        for line in iter(lines):

            if line.startswith("Default Profile"):
                node = 'default'
                continue

            if line.startswith("Secure Domain Router"):
                find_node = True
                continue

            if find_node:
                find = node_re.search(line)
                if find:
                    node = find.group('node')
                    find_node = False
                    continue
            if "Active Packages:" in line and node:
                start = True
                packages = self.active[node]
                continue

            if "Inactive Packages:" in line and node:
                start = True
                packages = self.inactive[node]
                continue

            if "Committed Packages:" in line and node:
                start = True
                packages = self.committed[node]
                continue

            if "Superceded Packages:" in line and node:
                start = True
                packages = self.superceded[node]
                continue

            if start:
                filename = line.strip()
                if filename in ["", "No packages."]:
                    start = False
                    find_node = True
                    continue
                packages.add(PackageInfo(filename))

    def is_consistent(self, node1, node2):
        return len(self.active[node1] ^ self.active[node2]) == 0

    def not_committed(self, node='default'):

        print("active: %s" % self.active[node])
        print("committed: %s" % self.committed[node])

        diff = self.active[node] - self.committed[node]
        print diff
        return diff


pies = """disk0:asr9k-9000v-nV-px-4.3.4
disk0:asr9k-asr901-nV-px-4.3.4
disk0:asr9k-asr903-nV-px-4.3.4
disk0:asr9k-doc-px-4.3.4
disk0:asr9k-fpd-px-4.3.4
disk0:asr9k-k9sec-px-4.3.4
disk0:asr9k-mcast-px-4.3.4
disk0:asr9k-mgbl-px-4.3.4
disk0:asr9k-mini-px-4.3.4
disk0:asr9k-mpls-px-4.3.4
disk0:asr9k-optic-px-4.3.4
disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
disk0:asr9k-video-px-4.3.4
disk0:hfr-mpls-px-5.1.1
disk0:hfr-mini-px-5.1.1
disk0:hfr-diags-px-5.1.1
disk0:hfr-doc-px-5.1.1
disk0:hfr-mcast-px-5.1.1
disk0:hfr-mgbl-px-5.1.1
disk0:hfr-mpls-px-5.1.1
disk0:hfr-k9sec-px-5.1.1
disk0:hfr-fpd-px-5.1.1"""


test = """
RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02#show  install active summary
Sun Mar 16 02:32:10.504 CET
Default Profile:
  SDRs:
    Owner
  Active Packages:
    disk0:asr9k-9000v-nV-px-4.3.4
    disk0:asr9k-asr901-nV-px-4.3.4
    disk0:asr9k-asr903-nV-px-4.3.4
    disk0:asr9k-doc-px-4.3.4
    disk0:asr9k-fpd-px-4.3.4
    disk0:asr9k-k9sec-px-4.3.4
    disk0:asr9k-mcast-px-4.3.4
    disk0:asr9k-mgbl-px-4.3.4
    disk0:asr9k-mini-px-4.3.4
    disk0:asr9k-mpls-px-4.3.4
    disk0:asr9k-optic-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
    disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
    disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
    disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
    disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
    disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
    disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
    disk0:asr9k-video-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCul93777-1.0.0

RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02#
"""


test2 = """
RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02#show  install active summary
Sun Mar 16 02:32:10.504 CET
Default Profile:
  SDRs:
    Owner
  Active Packages:
    disk0:asr9k-9000v-nV-px-4.3.4
    disk0:asr9k-asr901-nV-px-4.3.4
    disk0:asr9k-asr903-nV-px-4.3.4
    disk0:asr9k-doc-px-4.3.4
    disk0:asr9k-fpd-px-4.3.4
    disk0:asr9k-k9sec-px-4.3.4
    disk0:asr9k-mcast-px-4.3.4
    disk0:asr9k-mgbl-px-4.3.4
    disk0:asr9k-mini-px-4.3.4
    disk0:asr9k-mpls-px-4.3.4
    disk0:asr9k-optic-px-4.3.4
    disk0:asr9k-video-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCul93777-1.0.0

RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02#
"""
test3 = """RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02#admin show install
Sun Mar 16 09:24:55.889 CET
Secure Domain Router: Owner

  Node 0/RSP0/CPU0 [RP] [SDR: Owner]
    Boot Device: disk0:
    Boot Image: /disk0/asr9k-os-mbi-4.3.4.CSCum70202-1.0.0/0x100305/mbiasr9k-rsp3.vm
    Active Packages:
      disk0:asr9k-9000v-nV-px-4.3.4
      disk0:asr9k-asr901-nV-px-4.3.4
      disk0:asr9k-asr903-nV-px-4.3.4
      disk0:asr9k-doc-px-4.3.4
      disk0:asr9k-fpd-px-4.3.4
      disk0:asr9k-k9sec-px-4.3.4
      disk0:asr9k-mcast-px-4.3.4
      disk0:asr9k-mgbl-px-4.3.4
      disk0:asr9k-mini-px-4.3.4
      disk0:asr9k-mpls-px-4.3.4
      disk0:asr9k-optic-px-4.3.4
      disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
      disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
      disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
      disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
      disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
      disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
      disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
      disk0:asr9k-video-px-4.3.4

  Node 0/RSP1/CPU0 [RP] [SDR: Owner]
    Boot Device: disk0:
    Boot Image: /disk0/asr9k-os-mbi-4.3.4.CSCum70202-1.0.0/0x100305/mbiasr9k-rsp3.vm
    Active Packages:
      disk0:asr9k-9000v-nV-px-4.3.4
      disk0:asr9k-asr901-nV-px-4.3.4
      disk0:asr9k-asr903-nV-px-4.3.4
      disk0:asr9k-doc-px-4.3.4
      disk0:asr9k-fpd-px-4.3.4
      disk0:asr9k-k9sec-px-4.3.4
      disk0:asr9k-mcast-px-4.3.4
      disk0:asr9k-mgbl-px-4.3.4
      disk0:asr9k-mini-px-4.3.4
      disk0:asr9k-mpls-px-4.3.4
      disk0:asr9k-optic-px-4.3.4
      disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
      disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
      disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
      disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
      disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
      disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
      disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
      disk0:asr9k-video-px-4.3.4

  Node 0/0/CPU0 [LC] [SDR: Owner]
    Boot Device: mem:
    Boot Image: /disk0/asr9k-os-mbi-4.3.4.CSCum70202-1.0.0/lc/mbiasr9k-lc.vm
    Active Packages:
      disk0:asr9k-mcast-px-4.3.4
      disk0:asr9k-mini-px-4.3.4
      disk0:asr9k-mpls-px-4.3.4
      disk0:asr9k-optic-px-4.3.4
      disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
      disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
      disk0:asr9k-px-4.3.4.CSCul93777-1.0.0
      disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
      disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
      disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
      disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
      disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
      disk0:asr9k-video-px-4.3.4

  Node 0/1/CPU0 [LC] [SDR: Owner]
    Boot Device: mem:
    Boot Image: /disk0/asr9k-os-mbi-4.3.4.CSCum70202-1.0.0/lc/mbiasr9k-lc.vm
    Active Packages:
      disk0:asr9k-mcast-px-4.3.4
      disk0:asr9k-mini-px-4.3.4
      disk0:asr9k-mpls-px-4.3.4
      disk0:asr9k-optic-px-4.3.4
      disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
      disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
      disk0:asr9k-px-4.3.4.CSCul93777-1.0.0
      disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
      disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
      disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
      disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
      disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
      disk0:asr9k-video-px-4.3.4

  Node 0/3/CPU0 [LC] [SDR: Owner]
    Boot Device: mem:
    Boot Image: /disk0/asr9k-os-mbi-4.3.4.CSCum70202-1.0.0/lc/mbiasr9k-lc.vm
    Active Packages:
      disk0:asr9k-mcast-px-4.3.4
      disk0:asr9k-mini-px-4.3.4
      disk0:asr9k-mpls-px-4.3.4
      disk0:asr9k-optic-px-4.3.4
      disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
      disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
      disk0:asr9k-px-4.3.4.CSCul93777-1.0.0
      disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
      disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
      disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
      disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
      disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
      disk0:asr9k-video-px-4.3.4

RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02#"""


test4 = """RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02#show install summary
Sun Mar 16 09:52:39.681 CET
Default Profile:
  SDRs:
    Owner
  Active Packages:
    disk0:asr9k-9000v-nV-px-4.3.4
    disk0:asr9k-asr901-nV-px-4.3.4
    disk0:asr9k-asr903-nV-px-4.3.4
    disk0:asr9k-doc-px-4.3.4
    disk0:asr9k-fpd-px-4.3.4
    disk0:asr9k-k9sec-px-4.3.4
    disk0:asr9k-mcast-px-4.3.4
    disk0:asr9k-mgbl-px-4.3.4
    disk0:asr9k-mini-px-4.3.4
    disk0:asr9k-mpls-px-4.3.4
    disk0:asr9k-optic-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
    disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
    disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
    disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
    disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
    disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
    disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
    disk0:asr9k-video-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCul93777-1.0.0
  Inactive Packages:
    disk0:asr9k-mini-px-4.2.3
    disk0:asr9k-px-4.2.3.CSCum51429-1.0.0
    disk0:asr9k-px-4.2.3.CSCul66510-1.0.0
    disk0:asr9k-px-4.2.3.CSCuj88983-1.0.0
    disk0:asr9k-px-4.2.3.CSCuj34330-1.0.0
    disk0:asr9k-px-4.2.3.CSCui36695-1.0.0
    disk0:asr9k-px-4.2.3.CSCui33805-1.0.0
    disk0:asr9k-px-4.2.3.CSCui05685-1.0.0
    disk0:asr9k-px-4.2.3.CSCuh95891-1.0.0
    disk0:asr9k-px-4.2.3.CSCuh47453-1.0.0
    disk0:asr9k-px-4.2.3.CSCug69332-1.0.0
    disk0:asr9k-px-4.2.3.CSCug38659-1.0.0
    disk0:asr9k-px-4.2.3.CSCue31495-1.0.0
    disk0:asr9k-px-4.2.3.CSCue06569-1.0.0
    disk0:asr9k-px-4.2.3.CSCub82683-1.0.0
    disk0:asr9k-px-4.2.3.CSCub43419-1.0.0
    disk0:asr9k-px-4.2.3.CSCue14377-1.0.0
    disk0:asr9k-px-4.2.3.CSCug55767-1.0.0
    disk0:asr9k-fpd-px-4.2.3
    disk0:asr9k-doc-px-4.2.3
    disk0:asr9k-mgbl-px-4.2.3
    disk0:asr9k-mpls-px-4.2.3
    disk0:asr9k-mcast-px-4.2.3
    disk0:asr9k-k9sec-px-4.2.3
    disk0:asr9k-optic-px-4.2.3
    disk0:asr9k-video-px-4.2.3
    disk0:asr9k-9000v-nV-px-4.2.3
    disk0:asr9k-px-4.2.3.CSCuf98728-1.0.0
    disk0:asr9k-px-4.2.3.CSCuf51823-1.0.0
    disk0:asr9k-px-4.2.3.CSCuf32158-1.0.0
    disk0:asr9k-px-4.2.3.CSCue95361-1.0.0
    disk0:asr9k-px-4.2.3.CSCue90361-1.0.0
    disk0:asr9k-px-4.2.3.CSCue62728-1.0.0
    disk0:asr9k-px-4.2.3.CSCue60194-1.0.0
    disk0:asr9k-px-4.2.3.CSCue28217-1.0.0
    disk0:asr9k-px-4.2.3.CSCue23364-1.0.0
    disk0:asr9k-px-4.2.3.CSCue21593-1.0.0
    disk0:asr9k-px-4.2.3.CSCue21083-1.0.0
    disk0:asr9k-px-4.2.3.CSCud98419-1.0.0
    disk0:asr9k-px-4.2.3.CSCud87100-1.0.0
    disk0:asr9k-px-4.2.3.CSCud81249-1.0.0
    disk0:asr9k-px-4.2.3.CSCud73764-1.0.0
    disk0:asr9k-px-4.2.3.CSCud54598-1.0.0
    disk0:asr9k-px-4.2.3.CSCud54093-1.0.0
    disk0:asr9k-px-4.2.3.CSCud49605-1.0.0
    disk0:asr9k-px-4.2.3.CSCud41972-1.0.0
    disk0:asr9k-px-4.2.3.CSCud40419-1.0.0
    disk0:asr9k-px-4.2.3.CSCud37351-1.0.0
    disk0:asr9k-px-4.2.3.CSCud29892-1.0.0
    disk0:asr9k-px-4.2.3.CSCud16470-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc94820-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc84257-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc83830-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc66761-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc59715-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc47831-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc44733-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc35670-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc23551-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc20553-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc17410-1.0.0
    disk0:asr9k-px-4.2.3.CSCub96985-1.0.0
    disk0:asr9k-px-4.2.3.CSCub74517-1.0.0
    disk0:asr9k-px-4.2.3.CSCub22596-1.0.0
    disk0:asr9k-px-4.2.3.CSCue43628-1.0.0
    disk0:asr9k-px-4.2.3.CSCud39254-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc82062-1.0.0
  Committed Packages:
    disk0:asr9k-9000v-nV-px-4.3.4
    disk0:asr9k-asr901-nV-px-4.3.4
    disk0:asr9k-asr903-nV-px-4.3.4
    disk0:asr9k-doc-px-4.3.4
    disk0:asr9k-fpd-px-4.3.4
    disk0:asr9k-k9sec-px-4.3.4
    disk0:asr9k-mcast-px-4.3.4
    disk0:asr9k-mgbl-px-4.3.4
    disk0:asr9k-mini-px-4.3.4
    disk0:asr9k-mpls-px-4.3.4
    disk0:asr9k-optic-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
    disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
    disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
    disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
    disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
    disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
    disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
    disk0:asr9k-video-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCul93777-1.0.0
  Superceded Packages:
    No packages.

RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02#"""


test5 = """RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02(admin)#show install summary
Sun Mar 16 10:56:30.137 CET
Default Profile:
  SDRs:
    Owner
  Active Packages:
    disk0:asr9k-9000v-nV-px-4.3.4
    disk0:asr9k-asr901-nV-px-4.3.4
    disk0:asr9k-asr903-nV-px-4.3.4
    disk0:asr9k-doc-px-4.3.4
    disk0:asr9k-fpd-px-4.3.4
    disk0:asr9k-k9sec-px-4.3.4
    disk0:asr9k-mcast-px-4.3.4
    disk0:asr9k-mgbl-px-4.3.4
    disk0:asr9k-mini-px-4.3.4
    disk0:asr9k-mpls-px-4.3.4
    disk0:asr9k-optic-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
    disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
    disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
    disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
    disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
    disk0:asr9k-px-4.3.4.CSCum51429-1.0.0
    disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
    disk0:asr9k-video-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCul93777-1.0.0
  Inactive Packages:
    disk0:asr9k-mini-px-4.2.3
    disk0:asr9k-px-4.2.3.CSCum51429-1.0.0
    disk0:asr9k-px-4.2.3.CSCul66510-1.0.0
    disk0:asr9k-px-4.2.3.CSCuj88983-1.0.0
    disk0:asr9k-px-4.2.3.CSCuj34330-1.0.0
    disk0:asr9k-px-4.2.3.CSCui36695-1.0.0
    disk0:asr9k-px-4.2.3.CSCui33805-1.0.0
    disk0:asr9k-px-4.2.3.CSCui05685-1.0.0
    disk0:asr9k-px-4.2.3.CSCuh95891-1.0.0
    disk0:asr9k-px-4.2.3.CSCuh47453-1.0.0
    disk0:asr9k-px-4.2.3.CSCug69332-1.0.0
    disk0:asr9k-px-4.2.3.CSCug38659-1.0.0
    disk0:asr9k-px-4.2.3.CSCue31495-1.0.0
    disk0:asr9k-px-4.2.3.CSCue06569-1.0.0
    disk0:asr9k-px-4.2.3.CSCub82683-1.0.0
    disk0:asr9k-px-4.2.3.CSCub43419-1.0.0
    disk0:asr9k-px-4.2.3.CSCue14377-1.0.0
    disk0:asr9k-px-4.2.3.CSCug55767-1.0.0
    disk0:asr9k-fpd-px-4.2.3
    disk0:asr9k-doc-px-4.2.3
    disk0:asr9k-mgbl-px-4.2.3
    disk0:asr9k-mpls-px-4.2.3
    disk0:asr9k-mcast-px-4.2.3
    disk0:asr9k-k9sec-px-4.2.3
    disk0:asr9k-optic-px-4.2.3
    disk0:asr9k-video-px-4.2.3
    disk0:asr9k-9000v-nV-px-4.2.3
    disk0:asr9k-px-4.2.3.CSCuf98728-1.0.0
    disk0:asr9k-px-4.2.3.CSCuf51823-1.0.0
    disk0:asr9k-px-4.2.3.CSCuf32158-1.0.0
    disk0:asr9k-px-4.2.3.CSCue95361-1.0.0
    disk0:asr9k-px-4.2.3.CSCue90361-1.0.0
    disk0:asr9k-px-4.2.3.CSCue62728-1.0.0
    disk0:asr9k-px-4.2.3.CSCue60194-1.0.0
    disk0:asr9k-px-4.2.3.CSCue28217-1.0.0
    disk0:asr9k-px-4.2.3.CSCue23364-1.0.0
    disk0:asr9k-px-4.2.3.CSCue21593-1.0.0
    disk0:asr9k-px-4.2.3.CSCue21083-1.0.0
    disk0:asr9k-px-4.2.3.CSCud98419-1.0.0
    disk0:asr9k-px-4.2.3.CSCud87100-1.0.0
    disk0:asr9k-px-4.2.3.CSCud81249-1.0.0
    disk0:asr9k-px-4.2.3.CSCud73764-1.0.0
    disk0:asr9k-px-4.2.3.CSCud54598-1.0.0
    disk0:asr9k-px-4.2.3.CSCud54093-1.0.0
    disk0:asr9k-px-4.2.3.CSCud49605-1.0.0
    disk0:asr9k-px-4.2.3.CSCud41972-1.0.0
    disk0:asr9k-px-4.2.3.CSCud40419-1.0.0
    disk0:asr9k-px-4.2.3.CSCud37351-1.0.0
    disk0:asr9k-px-4.2.3.CSCud29892-1.0.0
    disk0:asr9k-px-4.2.3.CSCud16470-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc94820-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc84257-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc83830-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc66761-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc59715-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc47831-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc44733-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc35670-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc23551-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc20553-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc17410-1.0.0
    disk0:asr9k-px-4.2.3.CSCub96985-1.0.0
    disk0:asr9k-px-4.2.3.CSCub74517-1.0.0
    disk0:asr9k-px-4.2.3.CSCub22596-1.0.0
    disk0:asr9k-px-4.2.3.CSCue43628-1.0.0
    disk0:asr9k-px-4.2.3.CSCud39254-1.0.0
    disk0:asr9k-px-4.2.3.CSCuc82062-1.0.0
  Committed Packages:
    disk0:asr9k-9000v-nV-px-4.3.4
    disk0:asr9k-asr901-nV-px-4.3.4
    disk0:asr9k-asr903-nV-px-4.3.4
    disk0:asr9k-doc-px-4.3.4
    disk0:asr9k-fpd-px-4.3.4
    disk0:asr9k-k9sec-px-4.3.4
    disk0:asr9k-mcast-px-4.3.4
    disk0:asr9k-mgbl-px-4.3.4
    disk0:asr9k-mini-px-4.3.4
    disk0:asr9k-mpls-px-4.3.4
    disk0:asr9k-optic-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCui94441-1.0.0
    disk0:asr9k-px-4.3.4.CSCul39674-1.0.0
    disk0:asr9k-px-4.3.4.CSCum03261-1.0.0
    disk0:asr9k-px-4.3.4.CSCum43188-1.0.0
    disk0:asr9k-px-4.3.4.CSCum46796-1.0.0
    disk0:asr9k-px-4.3.4.CSCum70202-1.0.0
    disk0:asr9k-video-px-4.3.4
    disk0:asr9k-px-4.3.4.CSCul93777-1.0.0
  Superceded Packages:
    No packages.

RP/0/RSP0/CPU0:bdlk1-b12-asr9006-02(admin)#"""


if __name__ == '__main__':

    print("----------------- admin show install --------- ")
    packages = DevicePackages()
    packages.init_from_show_install(test3)

    print("ACTIVE: %s" % packages.active)
    print("INACTIVE: %s" % packages.inactive)
    print("COMMITTED: %s" % packages.committed)
    print("SUPERCEDED: %s" % packages.superceded)

    print packages.is_consistent("0/RSP0/CPU0", "0/RSP1/CPU0")

    print
    print("----------------- show install summary --------")
    packages = DevicePackages()
    packages.init_from_show_install(test4)

    print("ACTIVE: %s" % packages.active)
    print("INACTIVE: %s" % packages.inactive)
    print("COMMITTED: %s" % packages.committed)
    print("SUPERCEDED: %s" % packages.superceded)

    for pie in pies.split("\n"):
        # print "PIE %s" % pie
        p = PackageInfo(pie)
        p1 = copy.copy(p)
        p2 = copy.deepcopy(p)
        print p
        p.filename = "dupa"
        p.version = "2.2.2"
        print p.version
        print p.filename
        print p1
        print p1.filename
        print p1.version
        print p2
        print p2.filename
        print p2.version
        print p.platform
        print p.architecture
        print p.version

        p.filename = "disk0:hfr-k9sec-px-5.1.1"
        print p.platform
        print p.version
        print p._info

    packages = DevicePackages()
    packages.init_from_show_install(test5)

    print("NOT COMMITTED: %s" % packages.not_committed())
