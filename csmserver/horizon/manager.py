# =============================================================================
# manager.py
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

import logging
import os
import re
import condoor

import plugins


# decorator adding the current plugin name to the log message if plugin is executed
def plugin_log(func):
    def log_wrapper(self, message):
        func(self, message, "[{}] {}".format(
            self.current_plugin, message) if self.current_plugin else "{}".format(message))
    return log_wrapper


class PluginError(Exception):
    pass


# FIXME: Phases needs to be agreed with Alex
csm2plugin_phase_map = {
    "Pre-Upgrade": "PRE_UPGRADE",
    "Install Add": "ADD",
    "Remove": "REMOVE",
    "Activate": "UPGRADE",
    "Deactivate": "DEACTIVATE",
    "Commit": "COMMIT",
    "Post-Upgrade": "POST_UPGRADE"
}


class PluginsManager(object):
    error_pattern = re.compile("Error:    (.*)$", re.MULTILINE)

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

        self.current_plugin = None
        self._phase = csm2plugin_phase_map.get(self.csm_ctx.requested_action, None)
        if self._phase is None:
            self.csm_ctx.success = False
            self.csm_ctx.post_status("Action not supported")
            self.log("Action {} not supported".format(self.csm_ctx.requested_action))

    @property
    def phase(self):
        return self._phase

    def run(self):
        device = condoor.Connection(
            self.csm_ctx.host.hostname,
            self.csm_ctx.host_urls,
            log_dir=self.csm_ctx.log_directory
        )

        try:
            self.log("Device Discovery Pending")
            device.discovery()
        except condoor.ConnectionError as e:
            self.csm_ctx.post_status(e.message)
            return False

        self.log("Platform detected: {}".format(device.family))
        device.store_property("ctx", self.csm_ctx)

        try:
            self.log("Device Connection Pending")
            device.connect()
        except condoor.ConnectionError as e:
            self.csm_ctx.post_status(e.message)
            return False
        self.log("Device Connected Successfully")

        list_of_plugins = ", ".join(plugin.description for plugin in plugins.get_plugins_of_phase(self.phase))
        self.log("Plugins to be launched: {}".format(list_of_plugins))

        try:
            for plugin in plugins.get_plugins_of_phase(self.phase):
                self.log("Launching {} Plugin".format(plugin.description))
                self.current_plugin = plugin.description
                plugin.__class__.start(self, device)
                self.current_plugin = None
                self.log("Finished {} Plugin".format(plugin.description))

        except PluginError as e:
            self.csm_ctx.success = False
            self.csm_ctx.post_status(e.message)
            return False

        except (condoor.ConnectionError, condoor.CommandError) as e:
            self.csm_ctx.success = False
            self.csm_ctx.post_status(e.message)
            self.logger.error(e.message)
            return False

        except Exception as e:
            self.logger.error(e.__class__)
            self.logger.error(e.message)
            self.csm_ctx.success = False
            self.csm_ctx.post_status(e.message)
            return False

        finally:
            device.disconnect()

        self.csm_ctx.success = True
        return True

    @plugin_log
    def log(self, message, log_message):
        self.logger.info(log_message)
        self.csm_ctx.post_status(message)

    @plugin_log
    def info(self, message, log_message):
        self.logger.info(log_message)

    @plugin_log
    def error(self, message, log_message):
        self.logger.error(log_message)
        raise PluginError(message)

    @plugin_log
    def warning(self, message, log_message):
        self.logger.warning(log_message)

    def log_install_errors(self, output):
        errors = re.findall(PluginsManager.error_pattern, output)
        for line in errors:
            self.warning(line)
