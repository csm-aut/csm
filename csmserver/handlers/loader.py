# =============================================================================
# Copyright (c) 2015, Cisco Systems, Inc
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
from utils import import_class
from utils import get_software_platform
from utils import get_software_version
from utils import create_log_directory

from constants import UNKNOWN
from constants import get_log_directory

import condoor
import logging

import os


def discover_platform_info(ctx):
    try:
        log_dir = os.path.join(get_log_directory(), create_log_directory(ctx.host.connection_param[0].host_or_ip))
    except Exception:
        log_dir = None

    """Discover platform when added to CSM."""
    conn = condoor.Connection(name=ctx.hostname, urls=ctx.host_urls, log_level=logging.CRITICAL, log_dir=log_dir)
    try:
        conn.connect(force_discovery=True)
        ctx.host.family = conn.family
        ctx.host.platform = conn.platform
        ctx.host.software_platform = get_software_platform(family=conn.family, os_type=conn.os_type)
        ctx.host.software_version = get_software_version(conn.os_version)
        ctx.host.os_type = conn.os_type
        ctx.db_session.commit()
    finally:
        conn.disconnect()


def get_connection_handler_class(ctx):
    return import_class('handlers.base.BaseConnectionHandler')


def get_inventory_handler_class(ctx):
    if ctx.host.family == UNKNOWN:
        discover_platform_info(ctx)

    return import_class('handlers.base.BaseInventoryHandler')
    # Saved for later platform with variant
    # return import_class('handlers.platforms.%s.InventoryHandler' % ctx.host.software_platform)


def get_install_handler_class(ctx):
    if ctx.host.family == UNKNOWN:
        discover_platform_info(ctx)

    return import_class('handlers.base.BaseInstallHandler')
    # Saved for later platform with variant
    # return import_class('handlers.platforms.%s.InstallHandler' % ctx.host.software_platform)

