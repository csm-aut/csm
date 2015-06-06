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
import sys
import threading
import time 
import datetime

from database import DBSession
from sqlalchemy import and_

from models import Host
from models import InstallJob
from models import InstallJobHistory
from models import SystemOption
from models import logger
from models import get_download_job_key_dict

from constants import JobStatus
from constants import InstallAction

from threadpool import Pool
from threadpool import WorkUnit

from handlers.loader import get_inventory_handler_class 
from handlers.loader import get_install_handler_class 
from base import InstallContext

from utils import create_log_directory
from utils import is_empty

from mailer import send_install_status_email

import traceback

lock = threading.Lock()
in_progress_hosts = []

class SoftwareManager(threading.Thread):
    def __init__(self, name, num_threads=None):
        threading.Thread.__init__(self, name = name)
        
        db_session = DBSession()
        if num_threads is None:
            num_threads = SystemOption.get(db_session).install_threads
        
        # Set up the thread pool
        self.pool = Pool(num_threads)
    
    def run(self):
        while 1:
            time.sleep(20)
            self.dispatch()
    
    """
    In order for a scheduled install job to proceed, its dependency must be successfully completed
    and is present in the InstallJobHistory table.  It is possible that the dependency (install_job_id) 
    has multiple entries in the table.  This can happen when it takes multiple tries for the dependency 
    to become successful (i.e. after couple failed attempts).
    """
    def get_install_job_dependency_completed(self, db_session, install_job):
        return db_session.query(InstallJobHistory).filter(and_(
           InstallJobHistory.install_job_id == install_job.dependency, 
           InstallJobHistory.host_id == install_job.host_id,
           InstallJobHistory.status == JobStatus.COMPLETED)).all()
        
    def dispatch(self):
        db_session = DBSession()
        try:
            # Check if Scheduled Installs are allowed to run.
            if not can_install(db_session):
                return
                
            resultSet = db_session.query(InstallJob).filter(InstallJob.scheduled_time <= datetime.datetime.utcnow()).all()
            download_job_key_dict = get_download_job_key_dict()

            if len(resultSet)> 0:
                for install_job in resultSet:
                    if install_job.status != JobStatus.FAILED:
                        # If there is pending download, don't submit the install job
                        if is_pending_on_download(download_job_key_dict, install_job):
                            continue
                        
                        # This install job has a dependency, check if the expected criteria is met
                        if install_job.dependency is not None:
                            dependency_completed = self.get_install_job_dependency_completed(db_session, install_job)
                            # If the dependency has not been completed, don't proceed
                            if len(dependency_completed) == 0:
                                continue
                        
                        with lock:
                            # If another install job for the same host is already in progress,
                            # the install job will not be queued for processing
                            if install_job.host_id in in_progress_hosts:
                                continue
                        
                            in_progress_hosts.append(install_job.host_id)
                        
                        # Allow the install job to proceed
                        install_work_unit = InstallWorkUnit(install_job.id, install_job.host_id)
                        self.pool.submit(install_work_unit)
        except:
            # Purpose ignore.  Otherwise, it may generate continue exception
            pass
        finally:
            db_session.close()

def get_download_job_key(install_job, filename):
    return "{}{}{}{}".format(install_job.user_id, filename, install_job.server_id, install_job.server_directory)

def is_pending_on_download(download_job_key_dict, install_job):
    pending_downloads = install_job.pending_downloads.split(',')
    for filename in pending_downloads:
        download_job_key = get_download_job_key(install_job, filename)
        if download_job_key in download_job_key_dict:
            return True
    return False

def remove_host_from_in_progress(host_id):
    with lock:
        if host_id is not None and host_id in in_progress_hosts: in_progress_hosts.remove(host_id)
        
def can_install(db_session):
    # Check if scheduled jobs are allowed to run  
    return SystemOption.get(db_session).can_install
                
class InstallWorkUnit(WorkUnit):
    def __init__(self, job_id, host_id):
        self.job_id = job_id
        self.host_id = host_id
    
    def get_software(self, db_session, ctx):
        handler_class = get_inventory_handler_class(ctx.host.platform)
        if handler_class is None:
            logger.error('SoftwareManager: Unable to get handler for %s', ctx.host.platform)

        handler = handler_class()
        if handler.get_software(ctx.host, ctx.inactive_cli, ctx.active_cli, ctx.committed_cli):  
            # Update the time stamp
            ctx.host.inventory_job[0].set_status(JobStatus.COMPLETED)
            
    def process(self):
        db_session = DBSession()
        ctx = None
        try:                                  
            install_job = db_session.query(InstallJob).filter(InstallJob.id == self.job_id).first()    
            if install_job is None:
                # This is normal because of race condition. It means the job is already deleted (completed).
                return
             
            if not can_install(db_session):
                # This will halt this host that has already been queued
                return
            
            host = db_session.query(Host).filter(Host.id == self.host_id).first()
            if host is None:
                logger.error('Unable to retrieve host %s', self.host_id)
                return
            
            handler_class = get_install_handler_class(host.platform)
            if handler_class is None:
                logger.error('Unable to get handler for %s, install job %s', host.platform, self.job_id)
        
            install_job.start_time = datetime.datetime.utcnow()
            install_job.set_status(JobStatus.PROCESSING)            
            install_job.session_log = create_log_directory(host.connection_param[0].host_or_ip, install_job.id)
            db_session.commit()
           
            ctx = InstallContext(host, db_session, install_job)
            ctx.operation_id = get_last_operation_id(db_session, install_job)
           
            handler = handler_class()
            handler.execute(ctx)
            
            if ctx.success:    
                # Update the software
                self.get_software(db_session, ctx)                
                archive_install_job(db_session, ctx, install_job, JobStatus.COMPLETED)                
            else:
                archive_install_job(db_session, ctx, install_job, JobStatus.FAILED)
                
            # db_session.commit()
            
        except: 
            try:
                logger.exception('InstallManager hit exception - install job =  %s', self.job_id)
                archive_install_job(db_session, ctx, install_job, JobStatus.FAILED, trace=traceback.format_exc())
                # db_session.commit()
            except:
                logger.exception('InstallManager hit exception - install job = %s', self.job_id)
        finally:
            # Must remove the host from the in progress list
            remove_host_from_in_progress(self.host_id)
            db_session.close()     

def get_last_operation_id(db_session, install_activate_job, trace=None):
    operation_id = -1
    if install_activate_job.install_action == InstallAction.INSTALL_ACTIVATE:
        install_add_job = get_last_successful_install_job(db_session, install_activate_job.host_id)
        if install_add_job is not None:
            # Check if Last Install Add and Activate have the same packages.
            # If they have, then return the operation id.
            install_add_packages = install_add_job.packages.split(',') if not is_empty(install_add_job.packages) else []
            install_activate_packages = install_activate_job.packages.split(',') if not is_empty(install_activate_job.packages) else []
            if len(install_add_packages) == len(install_activate_packages):
                for install_activate_package in install_activate_packages:
                    if install_activate_package not in install_add_packages:
                        return operation_id
                return install_add_job.operation_id
            
    return operation_id

def get_last_successful_install_job(db_session, host_id):
    return db_session.query(InstallJobHistory). \
        filter((InstallJobHistory.host_id == host_id), and_(InstallJobHistory.install_action == InstallAction.INSTALL_ADD)). \
        order_by(InstallJobHistory.status_time.desc()).first()
    
def archive_install_job(db_session, ctx, install_job, job_status, trace=None):
    install_job.set_status(job_status)
    if trace is not None:
        install_job.trace = trace
        
    install_job_history = InstallJobHistory()
    install_job_history.install_job_id = install_job.id
    install_job_history.host_id = install_job.host_id
    install_job_history.install_action = install_job.install_action
    install_job_history.packages = install_job.packages
    install_job_history.scheduled_time = install_job.scheduled_time
    install_job_history.start_time = install_job.start_time
    install_job_history.set_status(job_status)
    install_job_history.session_log = install_job.session_log
    install_job_history.created_by = install_job.created_by
    install_job_history.trace = install_job.trace
    
    if ctx is not None:
        install_job_history.operation_id = ctx.operation_id

    # Only delete the install job if it is completed successfully. 
    # Failed job should still be retained in the InstallJob table.
    if job_status == JobStatus.COMPLETED:
        db_session.delete(install_job)
        
    db_session.add(install_job_history)
    db_session.commit()
    
    # Send notification error
    send_install_status_email(install_job_history) 
    
if __name__ == '__main__': 
    pass
