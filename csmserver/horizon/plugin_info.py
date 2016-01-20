# =============================================================================
# plugin_info
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

from ConfigParser import ConfigParser
from distutils.version import StrictVersion


class PluginInfo(object):

    def __init__(self, plugin_name, plugin_path):
        self.__details = ConfigParser()
        self.name = plugin_name
        self.path = plugin_path
        self.plugin_object = None
        self.categories = []
        self.error = None

    @property
    def details(self):
        return self.__details

    @details.setter
    def details(self, cf_details):
        backup_name = self.name
        backup_path = self.path
        self.__details = cf_details
        self.name = backup_name
        self.path = backup_path

    @property
    def name(self):
        return self.details.get("Core", "Name")

    @name.setter
    def name(self, name):
        if not self.details.has_section("Core"):
            self.details.add_section("Core")
        self.details.set("Core", "Name", name)

    @property
    def path(self):
        return self.details.get("Core", "Module")

    @path.setter
    def path(self, path):
        if not self.details.has_section("Core"):
            self.details.add_section("Core")
        self.details.set("Core", "Module", path)

    @property
    def platforms(self):
        return list(map(lambda s: s.strip(), self.details.get("CSM", "Platforms").split(",")))

    @platforms.setter
    def platforms(self, platforms):
        if not self.details.has_section("CSM"):
            self.details.add_section("CSM")
        self.details.set("CSM", "Platforms", ",".join(map(str, platforms)))

    @property
    def phases(self):
        return list(map(lambda s: s.strip(), self.details.get("CSM", "Phases").split(",")))

    @phases.setter
    def phases(self, phases):
        if not self.details.has_section("CSM"):
            self.details.add_section("CSM")
        self.details.set("CSM", "Phases", ",".join(map(str, phases)))

    @property
    def version(self):
        return str(StrictVersion(self.details.get("Documentation", "Version")))

    @version.setter
    def version(self, version_string):
        if isinstance(version_string, StrictVersion):
            version_string = str(version_string)
        if not self.details.has_section("Documentation"):
            self.details.add_section("Documentation")
        self.details.set("Documentation", "Version", version_string)

    @property
    def author(self):
        return self.details.get("Documentation", "Author")

    @author.setter
    def author(self, author):
        if not self.details.has_section("Documentation"):
            self.details.add_section("Documentation")
        self.details.set("Documentation", "Author", author)

    @property
    def description(self):
        return self.details.get("Documentation", "Description")

    @description.setter
    def description(self, description):
        if not self.details.has_section("Documentation"):
            self.details.add_section("Documentation")
        self.details.set("Documentation", "Description", description)

    def to_dict(self):
        info = {
            "name": self.name,
            "path": self.path,
            "platforms": self.platforms,
            "phases": self.phases,
            "version": self.version,
            "author": self.author,
            "description": self.description}
        return info

