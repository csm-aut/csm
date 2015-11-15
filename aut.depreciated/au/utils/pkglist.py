#==============================================================================
# pkglist.py - Utility pr parse pkglist file and prove the read data
#
# Copyright (c)  2014, Cisco Systems
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

protocols = ['tftp', 'ftp:', 'sftp']


def get_pkgs(pkg_lst):
    if isinstance(pkg_lst, list):
        return pkg_lst
    elif isinstance(pkg_lst, str):
        fd = open(pkg_lst, "r")
        pkg_names = fd.readlines()
        fd.close()
        pkg_list = [x for x in [p.split("#")[0].strip() for p in pkg_names if p] if x[:4] not in protocols]
        if pkg_list:
            pkg_list = [p for p in pkg_list if p]
            return pkg_list


def get_repo(pkg_lst_file):
    fd = open(pkg_lst_file, "r")
    pkg_names = fd.readlines()
    fd.close()
    repo = [x for x in [p.split("#")[0].strip()
                        for p in pkg_names if p] if x[:4] in protocols]
    if repo:
        repo = [p for p in repo if p]
        return repo[-1]
