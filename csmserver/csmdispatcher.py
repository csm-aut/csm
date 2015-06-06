# =============================================================================
# Copyright (c)  2015, Cisco Systems, Inc
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
from sim import InventoryManager
from sum import SoftwareManager
from sdm import DownloadManager

from scheduler import InventoryManagerScheduler

import os

def dispatch():
    inventory_manager = InventoryManager('Inventory Manager')
    inventory_manager.start()
    
    inventory_manager_scheduler = InventoryManagerScheduler('Inventory Manager Scheduler')
    inventory_manager_scheduler.start()
 
    software_manager = SoftwareManager('Software Manager')
    software_manager.start()
    
    download_manager = DownloadManager('Download Manager')
    download_manager.start()
    
    print('csmdispatcher started')
    
def process_count(processname):
    try:
        return os.popen("ps -Af").read().count(processname)
    except:
        return -1
    
if __name__ == '__main__':  
    if process_count('csmdispatcher') > 1:
        print('csmdispatcher is already running.')
    else:
        dispatch()