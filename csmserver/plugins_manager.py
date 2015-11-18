# =============================================================================
# plugins_manager.py
#
# Copyright (c)  2015, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
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

import plugins
import condor
import logging
import os

#from plugins import get_plugins_of_phase


class PluginError(Exception):
    pass

class PluginsManager(object):
    def __init__(self, csm_ctx):
        self.csm_ctx = csm_ctx
        self.logger = logging.getLogger("{}.plugin_manager".format(csm_ctx.host.hostname))

        try:
            log_level = csm_ctx.log_level
        except AttributeError:
            log_level = logging.DEBUG

        formatter = logging.Formatter('%(asctime)-15s %(levelname)8s: %(message)s')
        try:
            log_dir = csm_ctx.log_directory
        except AttributeError:
            log_dir = None

        if log_dir:
            # Create the log directory.
            if not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir)
                except IOError:
                    log_dir = "./"
            log_filename = os.path.join(log_dir, 'plugins.log')
            handler = logging.FileHandler(log_filename)

        else:
            handler = logging.StreamHandler()

        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(log_level)

        self.current_plugin = "Plugin Manager"

    def run(self):

        phase = None

        # FIXME: Phases needs to be agreed with Alex
        if self.csm_ctx.requested_action == "Pre-Upgrade":
            phase = "PRE_UPGRADE"

        if self.csm_ctx.requested_action == "Install Add":
            phase = "ADD"

        if self.csm_ctx.requested_action == "Remove":
            phase = "REMOVE"

        if self.csm_ctx.requested_action == "Activate":
            phase = "UPGRADE"

        if self.csm_ctx.requested_action == "Deactivate":
            phase = "DEACTIVATE"

        if self.csm_ctx.requested_action == "Commit":
            phase = "COMMIT"

        if self.csm_ctx.requested_action == "Post-Upgrade":
            phase = "POST_UPGRADE"

        if phase is None:
            self.csm_ctx.success = False
            self.csm_ctx.post_status("Action not supported")
            self.log("Action {} not supported".format(self.csm_ctx.requested_action))

        device = condor.Connection(self.csm_ctx.host.hostname, self.csm_ctx.host_urls,
                                 log_dir=self.csm_ctx.log_directory)
        try:
            self.log("Device Discovery Pending")
            device.detect_platform()
        except condor.exceptions.ConnectionError as e:
            self.csm_ctx.post_status(e.message)
            return False

        self.log("Platform detected: {}".format(device.family))
        device.store_property("ctx", self.csm_ctx)

        try:
            self.log("Device Connection Pending")
            device.connect()
        except condor.exceptions.ConnectionError as e:
            self.csm_ctx.post_status(e.message)
            return False
        self.log("Device Connected Successfully")

        list_of_plugins = ",".join(plugin.NAME for plugin in plugins.get_plugins_of_phase(phase))
        self.log("Plugins to be executed: {}".format(list_of_plugins))

        try:
            for plugin in plugins.get_plugins_of_phase(phase):
                plugin_desc = (plugin.DESCRIPTION[:45] + '..') if len(plugin.DESCRIPTION) > 35 else plugin.DESCRIPTION
                self.log("Executing plugin: {}".format(plugin_desc))
                self.current_plugin = plugin_desc
                plugin.__class__.start(self, device)
                self.current_plugin = "Plugin Manager"
                self.log("Plugin finished: {}".format(plugin_desc))

        except PluginError as e:
            self.csm_ctx.success = False
            self.csm_ctx.post_status(e.message)
            return False

        except condor.exceptions.ConnectionError as e:
            self.csm_ctx.success = False
            self.csm_ctx.post_status(e.message)
            return False

        finally:
            device.disconnect()

        self.csm_ctx.success = True
        return True

    def log(self, message):
        self.logger.info("[{}] {}".format(self.current_plugin, message))
        self.csm_ctx.post_status(message)

    def error(self, message):
        self.logger.error("[{}] {}".format(self.current_plugin, message))
        raise PluginError(message)

    def warning(self, message):
        self.logger.warning("[{}] {}".format(self.current_plugin, message))