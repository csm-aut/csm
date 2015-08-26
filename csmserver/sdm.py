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
import time
import threading 

from database import DBSession

from models import logger
from models import User
from models import DownloadJob
from models import Preferences
from models import SystemOption
from models import Server
from models import DownloadJobHistory
from server_helper import get_server_impl

from constants import JobStatus

from threadpool import Pool
from threadpool import WorkUnit

from bsd_service import BSDServiceHandler
from utils import untar
from utils import get_tarfile_file_list 

import os
import traceback
    
from constants import get_repository_directory

lock = threading.RLock()
in_progress_downloads = {}

class DownloadManager(threading.Thread):
    def __init__(self, name, num_threads=None):
        threading.Thread.__init__(self, name = name)
        
        if num_threads is None:
            num_threads = SystemOption.get(DBSession()).download_threads
        
        # Set up the thread pool
        self.pool = Pool(num_threads)
        
    def run(self):
        while 1:
            # This will be configurable
            time.sleep(20)
            self.dispatch()
     
    def dispatch(self):
        db_session = DBSession()
 
        try:
            download_jobs = db_session.query(DownloadJob).all()
         
            for download_job in download_jobs:
                if download_job.status != JobStatus.FAILED:
                    with lock:
                        # If another download job for the same image name is already in progress,
                        # the download job will not be queued for processing
                        if download_job.cco_filename in in_progress_downloads:
                            continue

                        in_progress_downloads[download_job.cco_filename] = download_job.cco_filename
                        
                    self.pool.submit(DownloadWorkUnit(download_job.id))
        except:
            logger.exception('Unable to dispatch download job')  
        finally:
            db_session.close()
 
class DownloadWorkUnit(WorkUnit):
    def __init__(self, job_id):
        self.job_id = job_id
        self.download_job = None
    
    def progress_listener(self, message):
        if self.download_job is not None:
            db_session = DBSession()
            self.download_job.set_status(message) 
            db_session.commit()
    
    def process(self):
        
        db_session = DBSession()        
        download_job = None
        try:           
            download_job = db_session.query(DownloadJob).filter(DownloadJob.id == self.job_id).first()    
            if download_job is None:
                logger.error('Unable to retrieve download job: %s' % self.job_id)
                return
            
            self.download_job = download_job
            output_file_path = get_repository_directory() + download_job.cco_filename
      
            # Only download if the image (tar file) is not in the downloads directory.
            # And, the image is a good one.
            if not self.is_tar_file_valid(output_file_path):
               
                user_id = download_job.user_id
                user = db_session.query(User).filter(User.id == user_id).first()
                if user is None:
                    logger.error('Unable to retrieve user: %s' % user_id)
               
                preferences = db_session.query(Preferences).filter(Preferences.user_id == user_id).first() 
                if preferences is None:
                    logger.error('Unable to retrieve user preferences: %s' % user_id)
                
                download_job.set_status(JobStatus.PROCESSING)
                db_session.commit() 
               
                bsd = BSDServiceHandler(username=preferences.cco_username, password=preferences.cco_password, 
                    image_name=download_job.cco_filename, PID=download_job.pid, MDF_ID=download_job.mdf_id, 
                    software_type_ID=download_job.software_type_id) 
                
                download_job.set_status('Preparing to download from cisco.com.')
                db_session.commit() 
                
                bsd.download(output_file_path, callback=self.progress_listener)         
                # Untar the file to the output directory
                tarfile_file_list = untar(output_file_path, get_repository_directory())
            else:
                tarfile_file_list = get_tarfile_file_list(output_file_path)
            
            # Now transfers to the server repository
            download_job.set_status('Transferring file to server repository.')
            db_session.commit() 
            
            server = db_session.query(Server).filter(Server.id == download_job.server_id).first()
            if server is not None:
                server_impl = get_server_impl(server) 
                for filename in tarfile_file_list:
                    server_impl.upload_file(get_repository_directory() + filename, filename, sub_directory=download_job.server_directory)       
            
            self.archive_download_job(db_session, download_job, JobStatus.COMPLETED) 
            db_session.commit()

        except:
            try:
                logger.exception('DownloadManager hit exception - download job = %s', self.job_id)   
                self.archive_download_job(db_session, download_job, JobStatus.FAILED, traceback.format_exc())
                db_session.commit()                
            except:
                logger.exception('DownloadManager hit exception - download job = %s', self.job_id)
        finally:
            with lock:
                if download_job is not None and \
                    download_job.cco_filename in in_progress_downloads: del in_progress_downloads[download_job.cco_filename]
            db_session.close()       

    """
    The tar file is considered valid if its corresponding .size file content
    equals to the size of the tar file.  It will be nice if we can have MD5 support.
    """
    def is_tar_file_valid(self, tarfile_path):
        try: 
            tarfile_size = os.path.getsize(tarfile_path)
            recorded_size = open(tarfile_path + '.size', 'r').read()
            if tarfile_size == int(recorded_size):
                return True
        except:
            return False
        
    def archive_download_job(self, db_session, download_job, job_status, trace=None):
        download_job.set_status(job_status)
        if trace is not None:
            download_job.trace = traceback.format_exc()
    
        download_job_history = DownloadJobHistory()
        download_job_history.cco_filename = download_job.cco_filename
        download_job_history.pid = download_job.pid
        download_job_history.mdf_id = download_job.mdf_id
        download_job_history.software_type_id = download_job.software_type_id
        download_job_history.set_status(job_status) 
        download_job_history.scheduled_time = download_job.scheduled_time
        download_job_history.server_id = download_job.server_id
        download_job_history.server_directory = download_job.server_directory
        download_job_history.created_by = download_job.created_by
        download_job_history.trace = download_job.trace
        
        # Only delete the download job if it is completed successfully. 
        # Failed job should still be retained in the DownloadJob table.
        if job_status == JobStatus.COMPLETED:
            db_session.delete(download_job)
        
        db_session.add(download_job_history)

if __name__ == '__main__':
    download_manager = DownloadManager('Download Manager')
    download_manager.start()
    