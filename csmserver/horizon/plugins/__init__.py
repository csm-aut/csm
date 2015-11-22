# =============================================================================
#
# Copyright (c) 2015, Cisco Systems
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
import sys
from inspect import isclass
from collections import defaultdict

# loading all the classes from the modules dynamically
path = os.path.dirname(os.path.abspath(__file__))
for py in [f[:-3] for f in os.listdir(path) if f.endswith('.py') and f != '__init__.py']:
    mod = __import__('.'.join([__name__, py]), fromlist=[py])
    classes = [getattr(mod, x) for x in dir(mod) if isinstance(getattr(mod, x), type)]
    for cls in classes:
        setattr(sys.modules[__name__], cls.__name__, cls)


# Added manually to preserve the order
plugin_classes = [
    SoftwareVersionPlugin,
    InstallDeactivatePlugin,
    InstallRemovePlugin,
    ConfigBackupPlugin,
    NodeStatusPlugin,
    DiskSpacePlugin,
    PingTestPlugin,
    NodeRedundancyPlugin,
    InstallAddPlugin,
    InstallActivatePlugin,
    ErrorCorePlugin,
    InstallCommitPlugin,
]

plugin_list = []
plugin_map = defaultdict(list)

plugin_platform_map = defaultdict(defaultdict)

plugin_types = ["DEACTIVATE", "REMOVE", "ADD", "UPGRADE", "PRE_UPGRADE", "PRE_UPGRADE_AND_POST_UPGRADE",
                "PRE_UPGRADE_AND_UPGRADE", "TURBOBOOT", "POST_UPGRADE", "COMMIT"]
phases = {
    "POLL": ["POLL"],
    "ADD": ["ADD"],
    "COMMIT": ["COMMIT"],
    "PRE_UPGRADE": [
        "PRE_UPGRADE", "PRE_UPGRADE_AND_POST_UPGRADE", "CONNECTION"
    ],
    "UPGRADE": [
        "PRE_UPGRADE_AND_UPGRADE", "UPGRADE"
    ],
    "TURBOBOOT": [
        "PRE_UPGRADE", "TURBOBOOT", "POST_UPGRADE"
    ],
    "POST_UPGRADE": [
        "POST_UPGRADE",
        "PRE_UPGRADE_AND_POST_UPGRADE"
    ],
    "ALL": [
        "PRE_UPGRADE",
        "PRE_UPGRADE_AND_POST_UPGRADE",
        "PRE_UPGRADE_AND_UPGRADE",
        "ADD",
        "UPGRADE",
        "POST_UPGRADE",
    ],
    "DEACTIVATE": ["DEACTIVATE", "POLL"],
    "REMOVE": ["REMOVE", "POLL"]
}


def is_plugin(o):
    return isclass(o) and issubclass(o, IPlugin) and o is not IPlugin


def add_plugin(plugin_class):
    plugin_cls = plugin_class()
    # plugin_classes.append(cls)
    plugin_list.append(plugin_cls)
    for phase in phases:
        if plugin_cls.TYPE in phases[phase]:
            plugin_map[phase].append(plugin_cls)


def get_plugins_of_phase(phase):
    return iter(plugin_map[phase])

for obj in plugin_classes:
    if is_plugin(obj):
        add_plugin(obj)

# for debug only
#for plugin in get_plugins_of_phase("ALL"):
#    print plugin.description