# =============================================================================
# Copyright (c) 2016, Cisco Systems, Inc
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
from database import DBSession
from models import logger
from models import Log
from models import SystemOption
from models import InventoryJob
from models import InventoryJobHistory
from models import InstallJobHistory
from models import DownloadJobHistory
from models import CreateTarJob

from constants import get_log_directory
from constants import JobStatus

import threading 
import sched
import datetime
import time
import shutil


class InventoryManagerScheduler(threading.Thread):
    def __init__(self, name):
        threading.Thread.__init__(self, name=name)
        
    def run(self):
        db_session = DBSession()   
        try:         
            system_option = SystemOption.get(db_session)            
            inventory_hour = system_option.inventory_hour
            db_session.close()
                        
            # Build a scheduler object that will look at absolute times
            scheduler = sched.scheduler(time.time, time.sleep)
            current_hour = datetime.datetime.now().hour
    
            # Put task for today at the designated hour.
            daily_time = datetime.time(inventory_hour)
            
            # If the scheduled time already passed, schedule it for tomorrow
            if current_hour > inventory_hour:
                first_time = datetime.datetime.combine(datetime.datetime.now() + datetime.timedelta(days=1), daily_time)
            else:
                first_time = datetime.datetime.combine(datetime.datetime.now(), daily_time)
            
            scheduler.enterabs(time.mktime(first_time.timetuple()), 1, self.scheduling, (scheduler, daily_time,))
           
            scheduler.run()
            
        except:
            logger.exception('InventoryManagerScheduler hit exception')
            db_session.close()
            
    def scheduling(self, scheduler, daily_time):
        
        # First, re-set up the scheduler for the next day the same time. It is important to have
        # this logic on the top so that if any error encountered below, the scheduling still works.
        t = datetime.datetime.combine(datetime.datetime.now() + datetime.timedelta(days=1), daily_time)
        scheduler.enterabs(time.mktime(t.timetuple()), 1, self.scheduling, (scheduler, daily_time,))
            
        db_session = DBSession()
        
        try:
            system_option = SystemOption.get(db_session)
            
            # If software inventory is enabled, submit the inventory jobs
            if system_option.enable_inventory:
                inventory_jobs = db_session.query(InventoryJob).all()

                if len(inventory_jobs) > 0:
                    for inventory_job in inventory_jobs:
                        inventory_job.pending_submit = True
                    db_session.commit()
                        
            # Check if there is any housekeeping work to do
            self.perform_housekeeping_tasks(db_session, system_option)
            
        except:
            logger.exception('InventoryManagerScheduler hit exception')
        finally:
            db_session.close()

    def perform_housekeeping_tasks(self, db_session, system_option):

        inventory_history_per_host = system_option.inventory_history_per_host
        install_history_per_host = system_option.install_history_per_host
        download_history_per_user = system_option.download_history_per_user
        total_system_logs = system_option.total_system_logs
    
        current_system_logs_count = db_session.query(Log).count()   
        system_logs_threshold = int(total_system_logs * 1.1)
        # If the current system logs count > the threshold (10% more than total_system_logs),
        # trim the log table back to the total_system_logs
        if current_system_logs_count > system_logs_threshold:
            num_records_to_purge = current_system_logs_count - total_system_logs
            # Select the logs by created_time in ascending order (older logs)
            logs = db_session.query(Log).order_by(Log.created_time.asc()).limit(num_records_to_purge)
            for log in logs:
                db_session.delete(log)
            db_session.commit()
    
        # Scanning the InventoryJobHistory table for records that should be deleted.
        skip_count = 0   
        current_host_id = -1
        
        inventory_jobs = db_session.query(InventoryJobHistory) \
            .order_by(InventoryJobHistory.host_id, InventoryJobHistory.created_time.desc())
    
        for inventory_job in inventory_jobs:
            if inventory_job.host_id != current_host_id:
                current_host_id = inventory_job.host_id
                skip_count = 0
            
            if skip_count >= inventory_history_per_host:
                # Delete the session log directory
                try:
                    if inventory_job.session_log is not None: 
                        shutil.rmtree(get_log_directory() + inventory_job.session_log)
                except:
                    logger.exception('InventoryManagerScheduler hit exception- inventory job = %s', inventory_job.id)
                    
                db_session.delete(inventory_job)
            
            skip_count += 1
                
        db_session.commit()
        
        # Scanning the InstallJobHistory table for records that should be deleted.
        skip_count = 0   
        current_host_id = -1
        
        install_jobs = db_session.query(InstallJobHistory) \
            .order_by(InstallJobHistory.host_id, InstallJobHistory.created_time.desc())
    
        for install_job in install_jobs:
            if install_job.host_id != current_host_id:
                current_host_id = install_job.host_id
                skip_count = 0
            
            if skip_count >= install_history_per_host:
                # Delete the session log directory
                try:
                    if install_job.session_log is not None:
                        shutil.rmtree(get_log_directory() + install_job.session_log)
                except:
                    logger.exception('InventoryManagerScheduler hit exception - install job = %s', install_job.id)
                
                db_session.delete(install_job)
            
            skip_count += 1
                
        db_session.commit()

        # Scanning the DownloadJobHistory table for records that should be deleted.
        skip_count = 0   
        current_user_id = -1
        
        download_jobs = db_session.query(DownloadJobHistory) \
            .order_by(DownloadJobHistory.user_id, DownloadJobHistory.created_time.desc())
    
        for download_job in download_jobs:
            if download_job.user_id != current_user_id:
                current_user_id = download_job.user_id
                skip_count = 0
            
            if skip_count >= download_history_per_user:
                db_session.delete(download_job)
            
            skip_count += 1
                
        db_session.commit()

        # Deleting old CreateTarJobs
        create_tar_jobs = db_session.query(CreateTarJob).all

        for create_tar_job in create_tar_jobs:
            if create_tar_job.status == JobStatus.COMPLETED or create_tar_job.status == JobStatus.FAILED:
                db_session.delete(create_tar_job)

        db_session.commit()
        
if __name__ == '__main__':
    pass