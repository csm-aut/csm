# =============================================================================
# plugin.py - Generic Plugin Class
#
# Copyright (c) 2014, Cisco Systems
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

import os


class PluginError(Exception):
    pass


class IPlugin(object):

    """
    This is a main Plugin template class providing interface to other plugins
    """
    NAME = "GENERIC"
    DESCRIPTION = "Generic Plugin"
    TYPE = None
    VERSION = "0.0.1"

    def __init__(self):
        self.stdout = open(os.devnull, 'w')
        self.csm_context = None

    def save_to_file(self, data, outfile):
        with open(outfile, "w") as f:
            f.write(data)
        return

    def describe(self):
        print(self.DESCRIPTION)

    def _start(self, job, device, *args, **kwargs):

        self.stdout = job.data['stdout']
        self.csm_ctx = device.get_property('ctx')
        self.device = device
        device.stdout = job.data['stdout']
        device.log_event.listen(self.log)
        self.separator()
        self.log("Plugin started for {}".format(device.name))

        self.start(device, *args, **kwargs)

        device.log_event.disconnect(self.log)
        self.log("Plugin finished for {} successfully".format(device.name))

    def start(self, device, *args, **kwargs):
        """
        Start the plugin
        Must be overridden by the plugin class child implementation
        """
        raise NotImplementedError

    def error(self, message):
        print("calling disconnect from plugin.py - error, device.disconnect()")
        self.device.disconnect()
        self.log("Disconnected...")
        raise PluginError(message)

    def warning(self, message):
        PluginError(message)

    def separator(self):
        self.stdout.write("\n{}\n".format("-" * 80))

    def log(self, message):
        try :
            self.stdout.write(
               "{}: {}\n".format(self.DESCRIPTION, message))
            if self.csm_ctx and len('Executing: ' + self.DESCRIPTION) < 45 :
                self.csm_ctx.post_status('Executing: ' + self.DESCRIPTION)

        except :
            pass
