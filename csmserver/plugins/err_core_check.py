# =============================================================================
#
# Copyright (c)  2015, Cisco Systems
# All rights reserved.
#
# Author: Prasad S R
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

from plugin import IPlugin


class ErrorCorePlugin(IPlugin):
    """
    ASR9k Post-upgrade check
    This pluging checks for errors, traceback or any core dump
    """
    NAME = "ERROR_TRACEBACK_CRASH_CHECK"
    DESCRIPTION = "Device log check"
    TYPE = "POST_UPGRADE"
    VERSION = "1.0.0"
    FAMILY = "ASR9K"

    # matching any errors, core and tracebacks
    _string_to_check_re = re.compile(
        "^(.*(?:[Ee][Rr][Rr][Oo][Rr]|Core for pid|Traceback).*)$", re.MULTILINE
    )

    @staticmethod
    def start(manager, device, *args, **kwargs):

        output = device.send("show logging", timeout=300)
        ctx = device.get_property("ctx")
        if ctx:
            store_dir = ctx.log_directory
            file_name = os.path.join(store_dir, "post_upgrade_log.log")
            IPlugin.save_to_file(output, file_name)
            manager.log("Device log stored to: {}".format(file_name))

        for match in re.finditer(ErrorCorePlugin._string_to_check_re, output):
            manager.warning(match.group())

        return True