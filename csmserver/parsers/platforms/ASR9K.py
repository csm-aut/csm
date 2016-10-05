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
import re

from base import inventory_pattern, BaseInventoryParser
from models import get_db_session_logger


class ASR9KInventoryParser(BaseInventoryParser):

    def parse_inventory_output(self, output):
        """
        lines = output.split('\n')
        i = 0
        while ("Name" not in lines[i] and "NAME:" not in lines[i]) and i < len(lines):
            i += 1

        while i < len(lines):
        """
        flags = re.MULTILINE
        flags |= re.IGNORECASE
        return [m.groupdict() for m in re.finditer(inventory_pattern, output, flags=flags)
                if 'Generic Fan' not in m.group('description')]

    def process_inventory(self, ctx):
        """
        For ASR9K IOS-XR.
        There is only one chassis in this case. It most likely shows up last in the
        output of "admin show inventory".
        Example:
        NAME: "chassis ASR-9006-AC", DESCR: "ASR 9006 4 Line Card Slot Chassis with V1 AC PEM"
        PID: ASR-9006-AC, VID: V01, SN: FOX1523H7HA
        """
        inventory_output = ctx.load_data('inventory')[0]
        inventory_data = self.parse_inventory_output(inventory_output)
        for i in xrange(len(inventory_data)-1, -1, -1):
            if "chassis" in inventory_data[i]['name']:
                return self.store_inventory(ctx, inventory_data, i)

        logger = get_db_session_logger(ctx.db_session)
        logger.exception('Failed to find chassis in inventory output for host {}.'.format(ctx.host.hostname))
        return
