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
from base import BaseInventoryParser
from models import get_db_session_logger


class CRSInventoryParser(BaseInventoryParser):

    def process_inventory(self, ctx):
        """
        For CRS.
        There can be more than one chassis in this case.
        Example for CRS:
        NAME: "Rack 0 - Chassis", DESCR: "CRS 16 Slots Line Card Chassis for CRS-16/S-B"
        PID: CRS-16-LCC-B, VID: V03, SN: FXS1804Q576
        """
        inventory_output = ctx.load_data('inventory')[0]
        inventory_data = self.parse_inventory_output(inventory_output)
        chassis_indices = []
        for i in xrange(0, len(inventory_data)):
            if "Chassis" in inventory_data[i]['name']:
                chassis_indices.append(i)
        if len(chassis_indices) > 0:
            return self.store_inventory(ctx, inventory_data, chassis_indices)
        else:
            logger = get_db_session_logger(ctx.db_session)
            logger.exception('Failed to find chassis in inventory output for host {}.'.format(ctx.host.hostname))
            return

    def store_inventory(self, ctx, inventory_data, chassis_indices):
        if len(chassis_indices) == 1:
            super(CRSInventoryParser, self).store_inventory(ctx, inventory_data, chassis_indices[0])
        return
