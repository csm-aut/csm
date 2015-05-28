# =============================================================================
# plugins_manager.py - plugin manager
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


import time

from au import plugins
from au.lib.global_constants import *

from au.lib import aulog


LOAD_AFTER_PLUGIN = 'load_after_plugin'
PLUGIN_PATH = ""
SUCCESS = 0
IGNORE = 2


class PluginsManager(object):

    """
    The plugins manager keeps a list of plugins instances
    """

    def __init__(self):
        self.active = []

        aulog.info("List of installed plugins:\n")

        for plugin in plugins.plugins:
            aulog.info(
                '\t{}{} ({}) Version: {}{}'.format(
                    bcolors.OKGREEN,
                    plugin.DESCRIPTION,
                    plugin.NAME,
                    plugin.VERSION,
                    bcolors.ENDC,
                )
            )
        aulog.info('\n')

    def get_phase(self, options):
        """
        IMHO it should be better moved outside the class
        """
        if options.preupgradeset:
            return "PRE_UPGRADE"
        if options.upgradeset:
            return "UPGRADE"
        if options.postupgradeset:
            return "POST_UPGRADE"
        if options.turboboot:
            return "TURBOBOOT"
        if options.deactivateset:
           return "DEACTIVATE"
        if options.removeset:
           return "REMOVE"
        return "ALL"

    def start_ex(self, job):
        print(job)
        print(type(job))
        print(dir(job))
        print(job.data)
        print(type(job.data['device']))

        #job.data['session'] = job.data['host'].session

        #device.execute_command('show version brief')

        for plugin in plugins.plugin_map["PRE_UPGRADE"]:
            plugin.start(**job.data)

    def start(self, **kwargs):
        """
        Starts all the plugins in order

        @throw PluginError when a plugin could not be initialized
        """
        # holds status of all plugins we run
        results = {}

        # common parameters we pass to all plugins
        host = kwargs['session']
        option = kwargs['options']
        kwargs['results'] = results
        plugin_type = ""

        phase = self.get_phase(option)
        aulog.debug("Running {} plugins".format(phase))

        # print "Setting term len to zero", status
        aulog.debug("Setting terminal len to 0")
        host.sendline("terminal len 0")
        prompt = kwargs.get('prompt', "#")
        failed = False
        retry = 0
        while not failed and retry < 3:
            index = host.expect_exact(
                [prompt, MORE, INVALID_INPUT, LOGIN_PROMPT_ERR,
                 pexpect.TIMEOUT], timeout=20)
            if index == 0:
                break
            if index == 1:
                host.sendline('q')
            if index == 4:
                failed = True
            retry += 1
        else:
            return 1  # ??? no clue what to return yet

        pno = 1
        for plugin in plugins.plugin_map[phase]:
            aulog.info(
                "++++" * 5 + bcolors.HEADER + " (%d) (%s) Check " % (pno, plugin.DESCRIPTION) + bcolors.ENDC + "++++" * 5)
            aulog.info("\nStarting => %s...." % plugin.DESCRIPTION)
            status = plugin.start(**kwargs)
            return_status = {plugin.NAME: status}
            results.update(return_status)

            if status == SUCCESS or status == SYSTEM_RELOADED or status == INSTALL_METHOD_PROCESS_RESTART:
                aulog.info(bcolors.OKGREEN + "\nPassed => %s\n" %
                           plugin.DESCRIPTION + bcolors.ENDC)
            elif status == IGNORE:
                aulog.info(bcolors.WARNING + "\nIgnoring => %s\n" %
                           plugin.DESCRIPTION + bcolors.ENDC)
            else:
                if not option.ignore_fail:
                    aulog.error(bcolors.FAIL + "\nFailed => %s\n" %
                                plugin.DESCRIPTION + bcolors.ENDC)
                else:
                    # TODO(klstanie): There is no reference to ignore error
                    aulog.ignore_error(
                        bcolors.FAIL + "\nFailed => %s\n" % i.DESCRIPTIONe + bcolors.ENDC)

            self.active.append(plugin)
            pno += 1
            time.sleep(1)

        if pno == 1:
            aulog.info(
                bcolors.HEADER + "++++" * 5 + " Notice " + "++++" * 5 + bcolors.ENDC)
            aulog.info(
                bcolors.WARNING + "Didn't find any plugins of type ** %s **" % plugin_type)

        aulog.info(
            bcolors.HEADER + "++++" * 5 + " Done " + "++++" * 5 + bcolors.ENDC)
        return status

    def stop(self):
        [plugin.stop() for plugin in self.active]


def main(args):
    # sys.exit(args)
    kwargs = {}
    if len(args) > 0:
        kwargs['repository'] = args[0]
    if len(args) > 1:
        kwargs['pkg-file-list'] = args[1]
    if len(args) > 2:
        kwargs['pre_upgrade_check'] = args[2]
    if len(args) > 3:
        kwargs['post_upgrade_check'] = args[3]
    plugin_manager = PluginsManager()
    plugins = plugin_manager.load_plugins()
    if plugins:
        plugin_manager.start(**kwargs)

if __name__ == '__main__':
    args = ['tftp://202.153.144.25/auto/tftp-blr-users3/mahessin/temp', 'tmp']
    main(args)
