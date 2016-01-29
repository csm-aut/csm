#!/usr/bin/env python
# =============================================================================
# plugin_tester.py
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

try:
    import click
except ImportError:
    print("Install click python package\n pip install click")
    exit()

from horizon.plugin_manager import PluginManager
from functools import partial
import urlparse
#import condoor
#from base import InstallContext
import logging
import time
import os

_PHASES = ["Pre-Upgrade", "Add", "Pre-Activate", "Activate", "Commit", "Deactivate", "Remove", "Post-Upgrade"]
_PLATFORMS = ["ASR9K", "NCS6K", "CRS"]

def print_plugin_info(plugins, detail=False):
    for plugin in plugins:
        click.echo("Name: {}".format(plugin.name))
        click.echo("Platforms: {}".format(", ".join(plugin.platforms)))
        click.echo("Phases: {}".format(", ".join(plugin.phases)))
        if detail:
            click.echo("Module: {}".format(plugin.path))
            click.echo("Author: {}".format(plugin.author))
            click.echo("Version: {}".format(plugin.version))

        click.echo("Description: {}\n".format(plugin.description))


def validate_phase(ctx, param, value):
    if value:
        if value.strip() not in _PHASES:
            raise click.BadParameter("The supported plugin phases are: {}".format(", ".join(_PHASES)))
    return value


class URL(click.ParamType):
    name = 'url'

    def convert(self, value, param, ctx):
        if not isinstance(value, tuple):
            parsed=urlparse.urlparse(value)
            if parsed.scheme not in ('telnet', 'ssh'):
                self.fail('invalid URL scheme (%s).  Only telnet and ssh URLs are '
                          'allowed' % parsed, param, ctx)
        return value


class InstallContext(object):
    _storage = {}

    def post_status(self, message):
        print("[CSM Status] {}".format(message))

    def save_data(self, key, value):
        #print("Saving [{}]={}".format(key, str(value[0])))
        self._storage[key] = value

    def load_data(self, key):
        #print("Loading [{}]".format(key))
        return self._storage.get(key, (None, None))


class Host(object):
    pass


@click.group()
def cli():
    """This script allows maintaining and executing the plugins."""
    pass


@cli.command("list", help="List all the plugins available.", short_help="List plugins")
@click.option("--platform", type=click.Choice(_PLATFORMS),
              help="Supported platform.")
@click.option("--phase", type=click.Choice(_PHASES),
              help="Supported phase.")
@click.option("--detail", is_flag=True,
              help="Display detailed information about each plugin.")
def plugin_list(platform, phase, detail):

    def plugin_filter(platform, phase, plugin_info):
        result = True
        if platform:
            result = platform in plugin_info.platforms
        if phase:
            result = result and (phase in plugin_info.phases)
        return result

    pm = PluginManager()
    pm.filter = partial(plugin_filter, platform, phase)
    nop = pm.locate_plugins()
    plugins = pm.load_plugins()

    if platform:
        click.echo("Plugins for platform: {}".format(platform))
    if phase:
        click.echo("Plugins for phase: {}".format(phase))

    click.echo("Number of plugins: {}\n".format(nop))
    print_plugin_info(plugins, detail)


@cli.command("run", help="Run specific plugin on the device.", short_help="Run plugin")
@click.option("--url", multiple=True, required=True, envvar='CSMPLUGIN_URLS', type=URL(),
              help='The connection url to the host (i.e. telnet://user:pass@hostname). '
                   'The --url option can be repeated to define multiple jumphost urls.')
@click.option("--phase", required=True, type=click.Choice(_PHASES),
              help="An install phase to run the plugin for.")
@click.option("--cmd", multiple=True, default=[],
              help='The command to be passed to the plugin in ')
@click.option("--log_dir", default="/tmp", type=click.Path(),
              help="An install phase to run the plugin for. If not path specified then default /tmp directory is used.")
@click.option("--package", default=[],
              help="Package for install operations. This package option can be repeated to provide multiple packages.")
@click.option("--repository_url", default=None,
              help="The package repository URL. (i.e. tftp://server/dir")
@click.argument("plugin_name", required=True, )
def plugin_run(url, phase, cmd, log_dir, package, repository_url, plugin_name):
    def plugin_filter(plugin_info, platform=None, phase=None, plugin_name=None):
        result = True
        if platform:
            result = platform in plugin_info.platforms
        if phase:
            result = result and (phase in plugin_info.phases)
        if plugin_name:
            result = result and (plugin_name in plugin_info.name)
        return result

    ctx = InstallContext()
    ctx.host = Host()
    ctx.host.hostname = "Hostname"
    ctx.host_urls = list(url)

    ctx.requested_action = phase
    ctx.log_directory = log_dir
    session_filename = os.path.join(log_dir, "session.log")
    plugins_filename = os.path.join(log_dir, "plugins.log")
    condoor_filename = os.path.join(log_dir, "condoor.log")

    if os.path.exists(session_filename):
        os.remove(session_filename)
    if os.path.exists(plugins_filename):
        os.remove(plugins_filename)
    if os.path.exists(condoor_filename):
        os.remove(condoor_filename)

    ctx.log_level = logging.DEBUG

    ctx.software_packages = list(package)
    ctx.server_repository_url = repository_url

    if cmd:
        ctx.custom_commands = list(cmd)

    pm = PluginManager()
    pm.run(ctx, plugin_name)

    click.echo("\n Plugin execution finieshd.\n")
    click.echo("Log files dir: {}".format(log_dir))
    click.echo(" {} - device session log".format(session_filename))
    click.echo(" {} - plugin execution log".format(plugins_filename))
    click.echo(" {} - device connection debug log".format(condoor_filename))

if __name__ == '__main__':
    cli()