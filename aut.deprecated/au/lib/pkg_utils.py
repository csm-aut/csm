# =============================================================================
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

import os
import re
from au.utils import pkglist

PIE = "pie"
ACTIVE = "active"
INACTIVE = "inactive"
COMMITTED = "committed"
ACTIVE_STR = "Active Packages:"
INACTIVE_STR = "Inactive Packages:"

pkg_name = "asr9k-mgbl-px.pie-4.2.3"
nn = "disk0:asr9k-mini-px-4.2.3"


class PackageClass(object):

    def __init__(self):
        # Platform or domain
        self.platform = None
        # Packge name
        self.pkg = None
        # Architecture
        self.arch = None
        # Release version
        self.version = None
        self.subversion = None
        # Package format
        self.format = None
        # Patch/maintenece version
        self.patch_ver = None
        # Requires or depends on
        self.requires = None
        #Supersedes or overrides
        self.supersedes = None
        # Partition where package exists
        self.partition = None


class NewPackage():

    def __init__(self, pkg_lst_file=None):
        self.inputfile = pkg_lst_file
        self.pkg_named_list = pkglist.get_pkgs(pkg_lst_file)
        self.pkg_list = []
        if self.pkg_named_list:
            self._update_pkgs()

    def _update_pkgs(self):
        for pkg_name in self.pkg_named_list:
            # Validate the package name
            pkg = self.validate_offbox_xrpie_pkg(pkg_name)
            if pkg:
                self.pkg_list.append(pkg)

    def validate_offbox_xrpie_pkg(self, pkg):
        # asr9k-px-4.3.2.CSCuj61599.pie
        # asr9k-mpls-px.pie-4.3.2
        # asr9k-asr9000v-nV-px.pie-5.2.2
        # asr9k-mcast-px.pie-5.2.2
        # asr9k-asr901-nV-px.pie-5.2.2
        # asr9k-mgbl-px.pie-5.2.2
        # asr9k-asr903-nV-px.pie-5.2.2

        #self.error("package 1",pkg)
        pkg_expr_2pkg = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)\.(?P<PKGFORMAT>\w+)-(?P<VERSION>\d+\.\d+\.\d+)')

        pkg_expr_2pkg_eng1 = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)\.(?P<PKGFORMAT>\w+)-(?P<VERSION>\d+\.\d+\.\d+\..*)\..*')

        pkg_expr_2pkg_inac = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+)')

        pkg_expr_2pkg_inac_eng = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+\.\d+\w+)')

        pkg_expr_2pkg_inac_noarch = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+)')

        pkg_expr_2pkg_inac_noarch_eng = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+\.\d+\w+)')

        pkg_expr = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<ARCH>p\w+)\.(?P<PKGFORMAT>\w+)-(?P<VERSION>\d+\.\d+\.\d+)')

        pkg_expr_eng = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<ARCH>p\w+)\.(?P<PKGFORMAT>\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\d+)')

        pkg_expr_inact = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<ARCH>p\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+)')

        pkg_expr_inact_eng_noarc=re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+\.\d+\w+)')

        pkg_expr_2pkg_inac = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+)')

        smu_expr_eng_int = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\d+.)\.(?P<PKGNAME>CSC\w+)(?P<PKGFORMAT>-)(?P<SMUVERSION>\d+\.\d+\.\d+.*)')
        smu_expr_eng_int1 = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+)\.(?P<PKGNAME>CSC\w+)(?P<PKGFORMAT>-)(?P<SMUVERSION>.*)') 
        smu_expr = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<ARCH>\w+)-(?P<VERSION>\d+\.\d+\.\d+)\.(?P<PKGNAME>\w+)\.(?P<PKGFORMAT>\w+)')
        smu_expr2 = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<ARCH>\w+)-(?P<VERSION>\d+\.\d+\.\d+)\.(?P<PKGNAME>\w+)-(?P<SMUVERSION>\d+\.\d+\.\d+)\.(?P<PKGFORMAT>\w+)')
        smu_expr3 = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<ARCH>\w+)-(?P<VERSION>\d+\.\d+\.\d+)\.(?P<PKGNAME>\w+)-(?P<PKGFORMAT>\d+\.\d+\.\d+)')

        pkg_expr_2pkg_int = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)\.(?P<PKGFORMAT>\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\d+[a-zA-Z])')
        pkg_expr_int = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<ARCH>p\w+)\.(?P<PKGFORMAT>\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\d+[a-zA-Z])')
        smu_expr_int = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<ARCH>\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\w*)\.(?P<PKGNAME>\w+)\.(?P<PKGFORMAT>\w+)')
        smu_expr2_int = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<ARCH>\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\w*)\.(?P<PKGNAME>\w+)-(?P<SMUVERSION>\d+\.\d+\.\d+\.\w*)\.(?P<PKGFORMAT>\w+)')
        pkg_expr_2pkg_eng = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<ARCH>p\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+\.\w+)')
        pkg_expr_2pkg_eng_test = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+-\w+)-(?P<ARCH>p\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+\.\w+)')

        pkg_expr_2pkg_sp = re.compile(
            r'(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+-\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+\.\w+-\d+\.\d+\.\d+)')

        pkg_expr_2pkg_sp1 = re.compile(
            r'(?P<PLATFORM>\w+)(?P<PKGNAME>-)(?P<ARCH>p\w+)(?P<PKGFORMAT>-)(?P<VERSION>\d+\.\d+\.\d+\.\w+-\d+\.\d+\.\d+)')

        pkg_arch="1"
        smu_ver="0"
        pkgobj = PackageClass()
        p = pkg_expr_2pkg_eng1.search(pkg)
        if not p:
            p = pkg_expr_2pkg.search(pkg)
        if not p:
            p = pkg_expr_2pkg_eng_test.search(pkg)
        if not p:
            p = pkg_expr_2pkg_sp.search(pkg)
        if not p:
            p = pkg_expr_2pkg_eng.search(pkg)
        if not p:
            p = pkg_expr_2pkg_int.search(pkg)
        if not p:
            p = pkg_expr_int.search(pkg)
        if not p:
            p = smu_expr2_int.search(pkg)
        if not p:
            p = pkg_expr_2pkg_inac.search(pkg)
        if not p:
            p = smu_expr_int.search(pkg)
        if not p:
            p = pkg_expr.search(pkg)
        if not p:
            p = smu_expr_eng_int.search(pkg)
            smu_ver="1"
        if not p:
            p = smu_expr_eng_int1.search(pkg)
            smu_ver="1"
        if not p:
            p = smu_expr.search(pkg)
            smu_ver=0
        if not p:
            p = smu_expr3.search(pkg)
            smu_ver=0
        if not p:
            p = smu_expr2.search(pkg)
            smu_ver=0
        if not p:
            p = pkg_expr_inact.search(pkg)
            smu_ver=0
        if not p:
            p = pkg_expr_inact_eng_noarc.search(pkg)
            pkg_arch="0"
            smu_ver=0
        if not p:
            p=pkg_expr_2pkg_inac_noarch.search(pkg)
            pkg_arch="0"
            smu_ver=0
        if p:
            if p.group("PKGFORMAT") == PIE or p.group("PKGFORMAT")== "-" or  p.group("PKGFORMAT") == "1.0.0" or p.group("PKGFORMAT") == ".":
                pkgobj.platform = p.group("PLATFORM")
                if "SUBPKGNAME" in p.groupdict().keys():
                    if p.group("PKGNAME")[:8] == 'asr9000v':
                        packagename = p.group(
                            "PKGNAME")[3:] + "-" + p.group("SUBPKGNAME")
                    else:
                        packagename = p.group(
                            "PKGNAME") + "-" + p.group("SUBPKGNAME")
                else:
                    packagename = p.group("PKGNAME")
                pkgobj.pkg = packagename
     
                if pkg_arch=="0":
                    pkgobj.arch=""
                else:
                    if p.group("PKGFORMAT") == PIE and packagename == "services-infra":
                        pkgobj.arch=""
                    else:
                        pkgobj.arch = p.group("ARCH")
                if p.group("PKGFORMAT") == ".":
                    pkgobj.format = p.group("PKGFORMAT")+p.group("PKGSUBFORMAT")
                else:
                    pkgobj.format = p.group("PKGFORMAT")
                if smu_ver=="1":
                    pkgobj.format = p.group("SMUVERSION")
                pkgobj.version = p.group("VERSION")
                return pkgobj

    def validate_xrrpm_pkg(self, pkg):
        pass


class OnboxPackage():

    def __init__(self, pkg_lst_file=None, pkg_state=None):

        self.inputfile = None
        self.pkg_list = []
        self.pkg_state = pkg_state
        if pkg_lst_file:
            self.inputfile = pkg_lst_file
            self.update_pkgs()

    def update_pkgs(self):
        if os.path.exists(self.inputfile):
            data = pkglist.get_pkgs(self.inputfile)
        else:
            data = self.inputfile.split("\n")

        start_pkg = False
        if data:
            for line in data:
                if line.find(self.pkg_state) < 0 and not start_pkg:
                    continue
                elif not start_pkg:
                    start_pkg = True

                pkg_name = line.strip()
                pkg = self.validate_xrpie_pkg(pkg_name)
                if not pkg:
                    pkg = self.validate_xrrpm_pkg(pkg_name)
                if pkg:
                    self.pkg_list.append(pkg)

    def validate_xrpie_pkg(self, pkg):
        # disk0:asr9k-mini-px-4.3.2
        # asr9k-px-4.2.3.CSCue60194-1.0.0
        # disk0:asr9k-px-5.3.1.06I.CSCub11122-1.0.0
        #self.error("package",pkg)
        pkg_expr_2pkg = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+.*)')

        pkg_expr_2pkg_eng = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\d+\w+)')

        pkg_expr_2pkg_inac = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+)')
        pkg_expr = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+)')
        pkg_expr_eng = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\d+\w+)')

        smu_expr = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+)\.(?P<PKGNAME>\w+)-(?P<SUBVERSION>\d+\.\d+\.\d+)')
        pkg_expr_int = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\d+[a-zA-Z])')
        smu_expr_int = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\w*)\.(?P<PKGNAME>\w+)-(?P<SUBVERSION>\d+\.\d+\.\d+.\w*)')
        smu_expr_internal = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<ARCH>p\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\w*)\.(?P<PKGNAME>\w+)-(?P<SUBVERSION>\d+\.\d+\.\d+)')
        pkg_expr_noarch = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<VERSION>\d+\.\d+\.\d+)')
        pkg_expr_noarch_eng = re.compile(
            r'(?P<DISK>\w+):(?P<PLATFORM>\w+)-(?P<PKGNAME>\w+)-(?P<SUBPKGNAME>\w+)-(?P<VERSION>\d+\.\d+\.\d+\.\d+\w+)')

        pkgobj = PackageClass()
        p = pkg_expr_2pkg_eng.search(pkg)
        if not p:
            p = pkg_expr_2pkg.search(pkg)
        if not p:
            p = pkg_expr_int.search(pkg)
        if not p:
            p = smu_expr_int.search(pkg)
        if not p:
            p = pkg_expr_eng.search(pkg)
        if not p:
            p = pkg_expr.search(pkg)
        if not p:
            p = smu_expr.search(pkg)
        if not p:
            p = smu_expr_internal.search(pkg)
        if not p:
            p = pkg_expr_noarch_eng.search(pkg)
        if not p:
            p = pkg_expr_noarch.search(pkg)
        if p:
            pkgobj.platform = p.group("PLATFORM")
            if "SUBPKGNAME" in p.groupdict().keys():
                packagename = p.group("PKGNAME") + "-" + p.group("SUBPKGNAME")
            else:
                packagename = p.group("PKGNAME")
            pkgobj.pkg = packagename
            pkgobj.partition = p.group("DISK")
            try:
               pkgobj.arch = p.group("ARCH")
            except:
               pkgobj.arch = "px"
            pkgobj.version = p.group("VERSION")
            if "SUBVERSION" in p.groupdict().keys():
                pkgobj.subversion = p.group("SUBVERSION")
            return pkgobj

    def validate_xrrpm_pkg(self, pkg):
        pass


# Packages in list1 but not in list 2
def missing_pkgs(list1, list2):
    missing_lst = []
    for pk1 in list1:
        missing = True
        for pk2 in list2:
            if pk1.pkg == pk2.pkg and pk1.version == pk2.version:
                missing = False
        if missing:
            missing_lst.append(pk1)
    return missing_lst


# Packages in list2 but not in list 1
def extra_pkgs(list1, list2):
    extra_lst = []
    for pk2 in list2:
        extra = True
        for pk1 in list1:
            if pk1.pkg == pk2.pkg and pk1.version == pk2.version:
                extra = False
        if extra:
            extra_lst.append(pk2)
    return extra_lst


def pkg_tobe_activated(added_pkgs, inactive_pkgs, active_pkgs):
    """
    Get list of added, active and inactive packages and determine
    of any needs to be activated or all are active.
    """
    SMU_RE = r'CSC\D\D\d\d\d'
    FP_RE = r'fp\d+'
    SP_RE = r'sp\d+'

    tobe_added = []
    # All added packages should either be active or inactive

    # Get the added package which is not in inactive state
   # missing_in_inactive = missing_pkgs(added_pkgs, inactive_pkgs)

    # If package to be activated is not in inactive state , see if that's
    # already active
   # if missing_in_inactive:
    #    missing_in_inactive = missing_pkgs(missing_in_inactive, active_pkgs)

 #   if not missing_in_inactive:
    for pk1 in added_pkgs:
        for pk2 in inactive_pkgs:
            if pk1.pkg == pk2.pkg and pk1.version == pk2.version:
                if re.match(SMU_RE, pk2.pkg) or re.match(FP_RE, pk2.pkg) or \
                       re.match(SP_RE, pk2.pkg):
                        # It's a SMU format is
                        # disk0:asr9k-px-4.3.2.CSCuj61599-1.0.0
                    pkg = "%s:%s-%s-%s.%s-%s" % (
                        pk2.partition, pk2.platform, pk2.arch,
                        pk2.version, pk2.pkg, pk2.subversion
                    )
                else:
                    if pk1.arch == "": 
                        pkg = "%s:%s-%s-%s" % (
                            pk2.partition, pk2.platform, pk2.pkg, 
                            pk2.version
                        )
                    else:
                        pkg = "%s:%s-%s-%s-%s" % (
                            pk2.partition, pk2.platform, pk2.pkg, pk2.arch,
                            pk2.version
                        )
 
                tobe_added.append(pkg)
    return tobe_added


def parse_xr_show_platform(output):
    inventory = {}
    lines = output.split('\n')

    for line in lines:
        line = line.strip()
        if len(line) > 0 and line[0].isdigit():
            node = line[:15].strip()
            entry = {
                'type': line[16:41].strip(),
                'state': line[42:58].strip(),
                'config_state': line[59:].strip()
            }
            inventory[node] = entry
    return inventory


def validate_xr_node_state(inventory, device):
    valid_state = [
        'IOS XR RUN',
        'PRESENT',
        'UNPOWERED',
        'READY',
        'UNPOWERED',
        'FAILED',
        'OK',
        'ADMIN DOWN',
        'DISABLED'
    ]
    for key, value in inventory.items():
        if 'CPU' in key:
            if value['state'] not in valid_state:
                break
    else:
        device.store_property('inventory', inventory)
        return True
    return False
