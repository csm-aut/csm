#==============================================================
# err_core_check.py  - Plugin for checking post upgrade error, tracebacks and crash.
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
from au.plugins import IPlugin

class ErrorCorePlugin(IPlugin):

    """
    ASR9k Post-upgrade check
    This pluging checks for errors, traceback or any core dump
    """
    NAME = "ERROR_TRACEBACK_CRASH_CHECK"
    DESCRIPTION = "Post upgrade error and core dump check..."
    TYPE = "POST_UPGRADE"
    VERSION = "0.0.1"

    def start(self, device, *args, **kwargs):
        """
        """
        success, output = device.execute_command("show logging")
        if not success:
            return False
        newstring = output.split("\n")
        for line in newstring[1:]:
            if "error" in line or "Error" in line or "ERROR" in line or "Core for pid" in line or "Traceback" in line:
                self.warning(
                    "ERROR/CORE/TRACEBACK DETECTED. Check device session log file '%s.session.log' for details" % device.name)
                return False
        return True
