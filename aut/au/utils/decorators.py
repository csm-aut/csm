# =============================================================================
# decorators.py
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

from au.utils.impl import add_label


def pre_upgrade(flag):
    def decorator(function):
        func = add_label(function, 'pre_upgrade', pre_upgrade=flag)
        return func
    return decorator


def upgrade(flag):
    def decorator(function):
        func = add_label(function, 'upgrade', upgrade=flag)
        return func
    return decorator


def post_upgrade(flag):
    def decorator(function):
        func = add_label(function, 'post_upgrade', post_upgrade=flag)
        return func
    return decorator


def cli_cmd_file(filename):
    def decorator(function):
        func = add_label(function, 'cmd_file', cmd_file=filename)
        return func
    return decorator


def repository(url):
    def decorator(function):
        func = add_label(function, 'repository', repository=url)
        return func
    return decorator


def pkg_file(filename):
    def decorator(function):
        func = add_label(function, 'pkg_file', pkg_file=filename)
        return func
    return decorator


def turbo_boot(flag):
    def decorator(function):
        func = add_label(function, 'turbo_boot', turbo_boot=flag)
        return func
    return decorator

def issu(flag):
    def decorator(function):
        func = add_label(function, 'issu', issu=flag)
        return func
    return decorator
