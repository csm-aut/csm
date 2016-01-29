# =============================================================================
# plugin_manager.py
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


# The plugin system is based on Yapsy package. Refer to http://yapsy.sourceforge.net/index.html
# Copyright (c) 2007-2015, Thibauld Nion


import logging
import os
import sys
import imp
import re
import time
import condoor

from plugin_locator import PluginLocator
from plugin_file_locator import PluginFileLocator

from plugin import Plugin
from csm_context import CSMContext


# decorator adding the current plugin name to the log message if plugin is executed
def plugin_log(func):
    def log_wrapper(self, message):
        func(self, message, "[{}] {}".format(
            self.current_plugin, message) if self.current_plugin else "{}".format(message))
    return log_wrapper


class PluginError(Exception):
    pass


RE_NON_ALPHANUM = re.compile("\W", re.U)


def normalize_plugin_name_for_module_name(plugin_name):
    plugin_name = plugin_name.decode("utf-8")
    if len(plugin_name) == 0:
        return "_"
    if plugin_name[0].isdigit():
        plugin_name = "_" + plugin_name
    ret = RE_NON_ALPHANUM.sub("_", plugin_name)
    ret = ret.encode("utf-8")
    return ret


class PluginManager(object):
    error_pattern = re.compile("Error:    (.*)$", re.MULTILINE)

    csm = CSMContext()

    def __init__(self, categories_filter=None, plugin_locator=None, plugin_dirs=None):

        self._set_logging()
        self.current_plugin = None

        if categories_filter is None:
            categories_filter = {"Default": Plugin}
        self.set_categories_filter(categories_filter)

        plugin_locator = plugin_locator if plugin_locator else PluginFileLocator()
        self.set_plugin_locator(plugin_locator)

        self._rejected_plugins = []

    def _set_logging(self, hostname="host", log_dir=None, log_level=logging.NOTSET):
        self.logger = logging.getLogger("{}.plugin_manager".format(hostname))
        formatter = logging.Formatter('%(asctime)-15s %(levelname)8s: %(message)s')
        if log_dir:
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


    @property
    def phase(self):
        if self.csm is None:
            raise RuntimeError("Plugin manager must run to get the the current phase")
        return self.csm.requested_action

    def run(self, csm, plugin_names=[]):
        self.csm = csm
        self._set_logging(self.csm.host.hostname, csm.log_directory, csm.log_level)

        plugin_names = plugin_names if hasattr(plugin_names, '__iter__') else [plugin_names]

        device = condoor.Connection(
            self.csm.host.hostname,
            self.csm.host_urls,
            log_dir=self.csm.log_directory
        )

        try:
            self.log("Device Discovery Pending")
            device.discovery()
        except condoor.ConnectionError as e:
            self.csm.post_status(e.message)
            return False
        self.log("Platform detected: {}".format(device.family))

        try:
            self.log("Device Connection Pending")
            device.connect()
        except condoor.ConnectionError as e:
            self.csm.post_status(e.message)
            return False
        self.log("Device Connected Successfully")

        if plugin_names:
            self.filter = lambda plugin_info: (device.family in plugin_info.platforms) and \
                                              (self.csm.requested_action in plugin_info.phases) and \
                                              (plugin_info.name in plugin_names)
        else:
            self.filter = lambda plugin_info: (device.family in plugin_info.platforms) and \
                                              (self.csm.requested_action in plugin_info.phases)

        nop = self.locate_plugins()
        self.log("Number of plugins: {}".format(nop))

        plugins = self.load_plugins()

        list_of_plugins = ", ".join(plugin.name for plugin in plugins)
        self.log("Plugins to be launched: {}".format(list_of_plugins))

        try:
            for plugin in plugins:
                self.log("Launching {} Plugin".format(plugin.name))
                self.current_plugin = plugin.name
                plugin.plugin_object.start(self, device)
                self.current_plugin = None
                self.log("Finished {} Plugin".format(plugin.name))

        except PluginError as e:
            self.csm.success = False
            self.csm.post_status(e.message)
            return False

        except (condoor.ConnectionError, condoor.CommandError) as e:
            self.csm.success = False
            self.csm.post_status(e.message)
            self.logger.error(e.message)
            return False

        except Exception as e:
            self.logger.error(e.__class__)
            self.logger.error(e.message)
            self.csm.success = False
            self.csm.post_status(e.message)
            return False

        finally:
            device.disconnect()

        self.csm.success = True
        return True

    @plugin_log
    def log(self, message, log_message):
        self.logger.info(log_message)
        self.csm.post_status(message)

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
        errors = re.findall(PluginManager.error_pattern, output)
        for line in errors:
            self.warning(line)

    def set_plugin_locator(self, plugin_locator):
        if isinstance(plugin_locator, PluginLocator):
            self._plugin_locator = plugin_locator
        else:
            raise TypeError("Unexpected format for plugin locator "
                            "({} is not an instance of PluginLocator)".format(plugin_locator))

    def get_plugin_locator(self):
        return self._plugin_locator

    def set_categories_filter(self, categories_filter):
        self.categories_interfaces = categories_filter.copy()
        self.category_mapping = {}
        self._category_file_mapping = {}
        for category in categories_filter:
            self.category_mapping[category] = []
            self._category_file_mapping[category] = []

    def get_categories(self):
        return list(self.category_mapping.keys())

    def remove_plugin_from_category(self, plugin, category_name):
        self.category_mapping[category_name].remove(plugin)

    def append_plugin_to_category(self, plugin, category_name):
        self.category_mapping[category_name].append(plugin)

    def get_plugins_of_category(self, category_name):
        return self.category_mapping[category_name][:]

    def get_all_plugins(self):
        all_plugins = set()
        for plugin_of_one_category in self.category_mapping.values():
            all_plugins.update(plugin_of_one_category)
        return list(all_plugins)

    def get_plugin_candidates(self):
        if not hasattr(self, "_candidates"):
            raise RuntimeError("locate_plugins must be called before get_plugin_candidate")
        return self._candidates[:]

    def load_plugins(self, callback=None):
        if not hasattr(self, "_candidates"):
            raise RuntimeError("locate_plugins must be called before append_plugin_candidates")

        processed_plugins = []
        for candidate_infofile, candidate_filepath, plugin_info in self._candidates:
            plugin_module_name_template = normalize_plugin_name_for_module_name(
                "csm_loaded_plugin_" + plugin_info.name) + "_{}"
            for plugin_name_suffix in range(len(sys.modules)):
                plugin_module_name = plugin_module_name_template.format(plugin_name_suffix)
                if plugin_module_name not in sys.modules:
                    break
            if candidate_filepath.endswith(".py"):
                candidate_filepath = candidate_filepath[:-3]

            if callback is not None:
                callback(plugin_info)

            if "__init__" in os.path.basename(candidate_filepath):
                candidate_filepath = os.path.dirname(candidate_filepath)

            try:
                if os.path.isdir(candidate_filepath):
                    candidate_module = imp.load_module(
                        plugin_module_name, None, candidate_filepath, ("py", "r", imp.PKG_DIRECTORY)
                    )
                else:
                    with open(candidate_filepath+".py", "r") as plugin_file:
                        candidate_module = imp.load_module(
                            plugin_module_name, plugin_file, candidate_filepath+".py", ("py","r",imp.PY_SOURCE)
                        )
            except Exception as e:
                exc_info = sys.exc_info()
                logging.error("Unable to import plugin: {}".format(candidate_filepath), exc_info=exc_info)
                plugin_info.error = exc_info
                processed_plugins.append(plugin_info)
                continue
            processed_plugins.append(plugin_info)
            if "__init__" in os.path.basename(candidate_filepath):
                sys.path.remove(plugin_info.path)

            for element in (getattr(candidate_module, name) for name in dir(candidate_module)):
                plugin_info_reference = None
                for category_name, category_interface in self.categories_interfaces.items():
                    try:
                        is_correct_subclass = issubclass(element, category_interface)
                    except Exception:
                        continue
                    if is_correct_subclass and element is not category_interface:
                        current_category = category_name
                        if candidate_infofile not in self._category_file_mapping[current_category]:
                            if not plugin_info_reference:
                                try:
                                    plugin_info.plugin_object = self.instanciate_element(element)
                                    plugin_info_reference = plugin_info
                                except Exception:
                                    exc_info = sys.exc_info()
                                    logging.error("Unable to create plugin object: {}".format(
                                        candidate_filepath), exc_info=exc_info)
                                    plugin_info.error = exc_info
                                    break
                            plugin_info.categories.append(current_category)
                            self.append_plugin_to_category(plugin_info_reference, current_category)
                            self._category_file_mapping[current_category].append(candidate_infofile)

        delattr(self, "_candidates")
        return processed_plugins

    def instanciate_element(self, element):
        return element()

    def filter_plugins(self):
        self._rejected_plugins = []
        for candidate_infofile, candidate_filepath, plugin_info, in self.get_plugin_candidates():
            if not self.filter(plugin_info):
                self.reject_plugin_candidate((candidate_infofile, candidate_filepath, plugin_info))

    def reject_plugin_candidate(self, plugin_tuple):
        if plugin_tuple in self._candidates:
            self.remove_plugin_candidates(plugin_tuple)
        if plugin_tuple not in self._rejected_plugins:
            self._rejected_plugins.append(plugin_tuple)

    def unreject_plugin_candidate(self, plugin_tuple):
        if plugin_tuple not in self._candidates:
            self.append_plugin_candidates(plugin_tuple)
        if plugin_tuple in self._rejected_plugins:
            self._rejected_plugins.remove(plugin_tuple)

    def remove_plugin_candidates(self, candidate_tuple):
        if not hasattr(self, "_candidates"):
            raise RuntimeError("locate_plugins must be called before remove_plugin_candidates")
        if candidate_tuple in self._candidates:
            self._candidates.remove(candidate_tuple)
        if candidate_tuple in self._rejected_plugins:
            self._rejected_plugins.remove(candidate_tuple)

    def append_plugin_candidates(self, candidate_tuple):
        if not hasattr(self, "_candidates"):
            raise RuntimeError("locate_plugins must be called before append_plugin_candidates")

        if self.filter(candidate_tuple[2]):
            if candidate_tuple not in self._candidates:
                self._candidates.append(candidate_tuple)
        else:
            if candidate_tuple not in self._rejected_plugins:
                self.reject_plugin_candidate(candidate_tuple)

    def get_rejected_plugins(self):
        return self._rejected_plugins[:]

    def locate_plugins(self):
        self._candidates, npc = self.get_plugin_locator().locate_plugins()
        self.filter_plugins()
        return len(self.get_plugin_candidates())


    def get_plugins_by_name(self, name, category="Default"):
        items = []
        if category in self.category_mapping:
            print self.category_mapping[category]
            for item in self.category_mapping[category]:
                if item.name == name:
                    items.append(item)
        return items

    # Plugin filter
    def _filter(self, plugin_info):
        return True
    filter = _filter

    # Storage API
    def save_data(self, key, data):
        """
        Stores (data, timestamp) tuple for key adding timestamp
        """
        self.csm.save_data(key, [data, time.time()])
        self.info("Key '{}' saved in CSM storage".format(key))

    def load_data(self, key):
        """
        Loads (data, timestamp) tuple for the key
        """
        result = self.csm.load_data(key)
        if result:
            self.info("Key '{}' loaded from CSM storage".format(key))
            if isinstance(result, list):
                return tuple(result)
            else:
                return result, None
        return None, None

    def save_to_file(self, file_name, data):
        """
        Save data to filename in the log_directory provided by CSM
        """
        store_dir = self.csm.log_directory
        full_path = os.path.join(store_dir, file_name)
        with open(full_path, "w") as f:
            f.write(data)
            self.info("File '{}' saved in CSM log directory".format(file_name))
            return full_path
        return None

    def load_from_file(self, file_name):
        """
        Load data from file where full path is provided as file_name
        """
        store_dir = self.csm.log_directory
        # full_path = os.path.join(store_dir, file_name)
        full_path = file_name
        with open(full_path, "r") as f:
            data = f.read()
            self.info("File '{}' loaded from CSM directory".format(os.path.basename(file_name)))
            return data
        return None

    def file_name_from_cmd(self, cmd, phase=None):
        #filename = re.sub(r"\s+", '-', cmd)
        filename = re.sub(r"\W+", '-', cmd)
        filename += "." + (str(self.phase).upper() if phase is None else str(phase).upper())
        filename += ".txt"
        return filename


