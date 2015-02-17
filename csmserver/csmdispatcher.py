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