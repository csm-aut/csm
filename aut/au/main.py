#!/usr/bin/env python
#
# ==============================================================================
# main.py - main module
#
# Copyright (c)  2014, Cisco Systems
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
# ==============================================================================

from au.device import Device
from au.lib.parser import parsecli
from au.manager import Manager

from au.utils.file import get_devices_from_txt
from au.utils.sigint import SigIntWatcher
# from au.utils.log import log_to_file
# from au.FileLogger import FileLogger
# from functools import partial
from au.Logfile import Logfile

import os
import sys

import datetime


def run():
    options, args, parser = parsecli()
    execute(options, args, parser, None)


def execute(options, args, parser, stdout=None, stderr=None):
    devices = []
    def mkdevices_from_file(filename):
        return get_devices_from_txt(options.devices)
    if not hasattr(options,'stdoutfile'):
        options.stdoutfile = sys.stdout

    if options.logdir:
        # Create the log directory.
        if not os.path.exists(options.logdir):
            print("Creating log directory '{}'...".format(options.logdir))
            try:
                os.makedirs(options.logdir)
            except IOError, e:
                parser.error(str(e))

    if options.outdir:
        # Create the log directory.
        if not os.path.exists(options.outdir):
            print("Creating command output directory '{}'...".format(
                options.outdir))
            try:
                os.makedirs(options.outdir)
            except IOError, e:
                parser.error(str(e))

    if not os.path.exists(options.outdir):
        try:
            os.makedirs(options.outdir)

        except IOError, e:
            parser.error(str(e))

    if options.device_url:
        if not type(options.device_url) == type([]) :
            urls = [options.device_url]
        else :
            urls = options.device_url
        devices.append(Device(urls))

    if options.devices:
        try:
            txt_devices = mkdevices_from_file(options.devices)
        except IOError, e:
            parser.error(str(e))
        except ValueError, e:
            parser.error(e)
        if not txt_devices:
            print("Warning: '{}' is empty.".format(options.devices))
        devices += txt_devices

    for device in devices:
        if options.session_log:
            filename = os.path.join(
                options.logdir, 'session.log'
            )
            device.session_log = Logfile(device.name, filename)

        device.output_store_dir = options.outdir

        if options.device_verbose:
            device.debug = options.device_verbose
            filename = os.path.join(
                options.logdir,'aut_debug.log'
            )
            device.stderr = Logfile(device.name, filename)
            device.store_property('ctx', options.ctx)
    manager = Manager(devices,
                      options,
                      options.verbose,
                      max_threads=options.max_threads
                      )
    manager.run()
    failed = manager.failed
    manager.destroy()

    return failed


def main():
    import traceback
    SigIntWatcher()
    try:
        failed = run()
        if failed :
            sys.exit('Error: %d actions failed.' % failed)

    except Exception as inst:
        print inst.__doc__
        print inst.message
        print traceback.format_exc()
        sys.exit(-1)

if __name__ == '__main__':
    main()
