# =============================================================================
# plugin_file_locator
#
# Copyright (c)  2016, Cisco Systems
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

import os
from plugin_info import PluginInfo
from plugin_locator import PluginLocator
from ConfigParser import ConfigParser


class PluginFileAnalyzer(object):
    def __init__(self, name):
        self.name = name

    def is_valid_plugin(self, filename):
        """
        Check if the resource found in filename is valid plugin.
        """
        raise NotImplementedError("is_valid_plugin must be implemented in {}".format(self))

    def get_infos_dict_from_plugin(self, dirpath, filename):
        """
        Returns the extracted plugin information as dictionary.
        This function ensures that "name" and "path" are provided.

        *dirpath* is the full path to the directory where the plugin file is
        *filename* is the name (basename) of the plugin file.

        """
        raise NotImplementedError("get_infors_dict_from_plugin must be implemented in {}".format(self))


class PluginFileAnalyzerWithInfoFile(PluginFileAnalyzer):

    def __init__(self, name, extensions="plugin"):
        PluginFileAnalyzer.__init__(self, name)
        self.set_plugin_info_extension(extensions)

    def set_plugin_info_extension(self, extensions):
        if not isinstance(extensions, tuple):
            extensions = (extensions, )
        self.expected_extensions = extensions

    def is_valid_plugin(self, filename):
        for extension in self.expected_extensions:
            if filename.endswith(".{}".format(extension)):
                return True
        else:
            return False

    def get_plugin_name_and_module_from_stream(self, infofile_object, candidate_infofile=None):
        config_parser = ConfigParser()
        try:
            config_parser.readfp(infofile_object)
        except Exception as e:
            #logging.debug("Could not parse the plugin file '{}'. Exception was raised: {}".format(
            #    candidate_infofile, e
            #))
            pass
        if not config_parser.has_section("Core"):
            #logging.debug("Plugin info file has no 'Core' section in {}".format(candidate_infofile))
            return None, None, None
        if not config_parser.has_option("Core", "Name"):
            #logging.debug("Plugin info file has no 'Core' section in {}".format(candidate_infofile))
            return None, None, None

        name = config_parser.get("Core", "Name")
        name.strip()
        return name, config_parser.get("Core", "Module"), config_parser

    def _extract_core_plugin_info(self, directory, filename):
        if not isinstance(filename, basestring):
            name, module_name, config_parser = self.get_plugin_name_and_module_from_stream(filename)
        else:
            candidate_infofile_path = os.path.join(directory, filename)
            with open(candidate_infofile_path) as candidate_infofile:
                name, module_name, config_parser = self.get_plugin_name_and_module_from_stream(
                    candidate_infofile, candidate_infofile_path)

        if (name, module_name, config_parser) == (None, None, None):
            return None, None
        infos = {"name": name, "path": os.path.join(directory, module_name)}
        return infos, config_parser

    def _extract_basic_plugin_info(self, directory, filename):
        infos, config_parser = self._extract_core_plugin_info(directory, filename)
        if infos and config_parser and config_parser.has_section("Documentation"):
            if config_parser.has_option("Documentation", "Author"):
                infos["author"] = config_parser.get("Documentation", "Author")
            if config_parser.has_option("Documentation", "Version"):
                infos["version"] = config_parser.get("Documentation", "Version")
            if config_parser.has_option("Documentation", "Website"):
                infos["website"] = config_parser.get("Documentation", "Website")
            if config_parser.has_option("Documentation", "Description"):
                infos["description"] = config_parser.get("Documentation", "description")

        return infos, config_parser


    def get_infos_dict_from_plugin(self, dirpath, filename):
        """
        Returns the extracted plugin information as a directory.
        This functions ensures that "name" and "path" are provided.
        """
        infos, config_parser = self._extract_basic_plugin_info(dirpath, filename)
        if not infos or infos.get("name", None) is None:
            raise ValueError("Missing plugin name in extracted information")
        if not infos or infos.get("path", None) is None:
            raise ValueError("Missing plugin path in extracted information")
        return infos, config_parser


class PluginFileLocator(PluginLocator):
    def __init__(self, analyzers=None, plugin_info_cls=PluginInfo):
        self._discovered_plugins = {}
        self.set_plugin_places(None)
        self._analyzers = analyzers
        if self._analyzers is None:
            self._analyzers = [PluginFileAnalyzerWithInfoFile("info_extension")]
        self._default_plugin_info_cls = plugin_info_cls
        self._plugin_info_cls_map = {}
        self.recursive = True

    def _get_info_for_plugin_from_analyzer(self, analyzer, dirpath, filename):
        """
        Return instance of plugin_info_cls class filled with data extracted by the analyzer

        May return None if the analyzer fails to extract any info
        """
        plugin_info_dict, config_parser = analyzer.get_infos_dict_from_plugin(dirpath, filename)
        if plugin_info_dict is None:
            return None
        plugin_info_cls = self._plugin_info_cls_map.get(analyzer.name, self._default_plugin_info_cls)
        plugin_info = plugin_info_cls(plugin_info_dict["name"], plugin_info_dict["path"])
        plugin_info.details = config_parser
        return plugin_info

    def locate_plugins(self):
        _candidates = []
        _discovered = {}
        for directory in map(os.path.abspath, self.plugin_places):
            if not os.path.isdir(directory):
                #logging.debug("Skipping {} (not a directory)".format(directory))
                continue
            if self.recursive:
                debug_txt_mode = "recursively"
                walk_iter = os.walk(directory, followlinks=True)
            else:
                debug_txt_mode = "non-recursively"
                walk_iter = [(directory, [], os.listdir(directory))]
            #logging.debug("Walking {} into directory: '{}'".format(debug_txt_mode, directory))
            for item in walk_iter:
                dirpath = item[0]
                for filename in item[2]:
                    for analyzer in self._analyzers:
                        if not analyzer.is_valid_plugin(filename):
                            #logging.debug("{} is not valid plugin for strategy {}".format(filename, analyzer.name))
                            continue
                        candidate_infofile = os.path.join(dirpath, filename)
                        if candidate_infofile in _discovered:
                            #logging.debug("{} with strategy {} rejected because already discovered".format(
                            #    candidate_infofile, analyzer.name
                            #))
                            continue
                        #logging.debug("{} found a candidate: {}".format(self.__class__.__name__, candidate_infofile))
                        plugin_info = self._get_info_for_plugin_from_analyzer(analyzer, dirpath, filename)
                        if plugin_info is None:
                            #logging.debug("Plugin candidate '{}' rejected by strategy '{}'".format(
                            #    candidate_infofile, analyzer.name))
                            break
                        if os.path.isdir(plugin_info.path):
                            candidate_filepath = os.path.join(plugin_info.path, "__init__")
                            for _file in os.listdir(plugin_info.path):
                                if _file.endswith(".py"):
                                    self._discovered_plugins[os.path.join(plugin_info.path, _file)] = candidate_filepath
                                    _discovered[os.path.join(plugin_info.path, _file)] = candidate_filepath
                        elif (plugin_info.path.endswith(".py") and os.path.isfile(plugin_info.path)) or \
                                os.path.isfile(plugin_info.path + ".py"):
                            candidate_filepath = plugin_info.path
                            if candidate_filepath.endswith(".py"):
                                candidate_filepath = candidate_filepath[:-3]
                            self._discovered_plugins[".".join((plugin_info.path, "py"))] = candidate_filepath
                            _discovered[".".join((plugin_info.path, "py"))] = candidate_filepath
                        else:
                            #logging.error("Plugin candidate rejected: cannot "
                            #              "find the file or directory module for {}".format(candidate_filepath))
                            break
                        _candidates.append((candidate_infofile, candidate_filepath, plugin_info))
                        _discovered[candidate_infofile] = candidate_filepath
                        self._discovered_plugins[candidate_infofile] = candidate_filepath
        return _candidates, len(_candidates)

    def set_plugin_places(self, directories_list):
        """
        Set the list of directories where to look for plugin places.
        """
        if directories_list is None:
            directories_list = [os.path.dirname(__file__)]
        self.plugin_places = directories_list

    def update_plugin_places(self, directories_list):
        """
        Updates the list of directories where to look for plugin places.
        """
        self.plugin_places = list(set.union(set(directories_list), set(self.plugin_places)))

    def gather_core_plugin_info(self, directory, filename):
        """
        Return a ``PluginInfo`` as well as the ``ConfigParser`` used to build it
        """
        for analyzer in self._analyzers:
            if not analyzer.is_valid_plugin(filename):
                continue
            plugin_info = self._get_info_for_plugin_from_analyzer(analyzer, directory, filename)
            return plugin_info, plugin_info.details

        return None, None