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
from eXR import EXRInventoryParser
from models import get_db_session_logger


class NCS1K5KInventoryParser(EXRInventoryParser):

    def process_inventory(self, ctx):
        """
        For NCS1K and NCS5K.
        There is only one chassis in this case. It most likely shows up first in the
        output of "admin show inventory".
        Example for NCS1K:
        Name: Rack 0                Descr: Network Convergence System 1000 Controller
        PID: NCS1002                VID: V01                   SN: CHANGE-ME-

        Example for NCS5K:
        Name: Rack 0                Descr:
        PID: NCS-5002               VID: V01                   SN: FOC1946R0DH
        """
        inventory_output = ctx.load_data('inventory')[0]
        inventory_data = self.parse_inventory_output(inventory_output)
        for i in xrange(0, len(inventory_data)):
            if "Rack 0" in inventory_data[i]['name']:
                return self.store_inventory(ctx, inventory_data, i)

        logger = get_db_session_logger(ctx.db_session)
        logger.exception('Failed to find chassis in inventory output for host {}.'.format(ctx.host.hostname))
        return
