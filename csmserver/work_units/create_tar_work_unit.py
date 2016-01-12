from multi_process import WorkUnit

from models import Server
from models import CreateTarJob

from utils import make_file_writable

from constants import get_repository_directory, get_temp_directory
from constants import JobStatus

from server_helper import get_server_impl

import os
import shutil
import errno
import stat
import datetime
import tarfile

class CreateTarWorkUnit(WorkUnit):
    def __init__(self, job_id):
        WorkUnit.__init__(self)

        self.job_id = job_id
        self.upload_progress = 0

    def start(self, db_session, logger, process_name):
        self.db_session = db_session
        try:
            self.create_tar_job = self.db_session.query(CreateTarJob).filter(CreateTarJob.id == self.job_id).first()
            if self.create_tar_job is None:
                logger.error('Unable to retrieve create tar job: %s' % self.job_id)
                return

            self.create_tar_job.set_status(JobStatus.PROCESSING)

            server_id = self.create_tar_job.server_id
            server_directory = self.create_tar_job.server_directory
            source_tars = self.create_tar_job.source_tars
            contents = self.create_tar_job.contents
            additional_packages = self.create_tar_job.additional_packages
            new_tar_name = self.create_tar_job.new_tar_name
            created_by = self.create_tar_job.created_by

            date_string = datetime.datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")

            repo_dir = get_repository_directory()
            temp_path = get_temp_directory() + str(date_string)
            new_tar_path = os.path.join(temp_path, str(date_string))

            try:
                if not os.path.exists(temp_path):
                    self.create_tar_job.set_status('Creating temporary directories.')
                    self.db_session.commit()
                    os.makedirs(temp_path)
                    os.makedirs(new_tar_path, 7777)

                # Untar source tars into the temp/timestamp directory
                if source_tars:
                    self.create_tar_job.set_status('Extracting from source tar files.')
                    self.db_session.commit()
                    for source in source_tars.split(','):
                        with tarfile.open(os.path.join(repo_dir, source)) as tar:
                            tar.extractall(temp_path)

                # Copy the selected contents from the temp/timestamp directory
                # to the new tar directory
                if contents:
                    self.create_tar_job.set_status('Copying selected tar contents.')
                    self.db_session.commit()
                    for f in contents.strip().split(','):
                        _, filename = os.path.split(f)
                        shutil.copy2(os.path.join(temp_path, filename), new_tar_path)

                # Copy the selected additional packages from the repository to the new tar directory
                if additional_packages:
                    self.create_tar_job.set_status('Copying selected additional files.')
                    for pkg in additional_packages.split(','):
                        self.db_session.commit()
                        shutil.copy2(os.path.join(repo_dir, pkg), new_tar_path)

                self.create_tar_job.set_status('Tarring new file.')
                self.db_session.commit()
                tarname = os.path.join(temp_path, new_tar_name)
                shutil.make_archive(tarname, format='tar', root_dir=new_tar_path)
                make_file_writable(os.path.join(new_tar_path, tarname) + '.tar')

                server = self.db_session.query(Server).filter(Server.id == server_id).first()
                if server is not None:
                    self.create_tar_job.set_status('Uploading tar file to external repository.')
                    self.db_session.commit()
                    server_impl = get_server_impl(server)
                    #if new_tar_name in server_impl.get_file_list():
                    #print server_impl.get_file_list()
                    #files, _ = server_impl.get_file_list()
                    if new_tar_name in server_impl.get_file_list():
                        server_impl.delete_file(new_tar_name)
                    #print server_impl.get_file_list()
                    server_impl.upload_file(tarname + '.tar', new_tar_name + ".tar", sub_directory=server_directory,
                                            callback=self.progress_listener)

                self.create_tar_job.set_status('Removing temporary directories.')
                self.db_session.commit()
                shutil.rmtree(temp_path, onerror=self.handleRemoveReadonly)
                self.create_tar_job.set_status(JobStatus.COMPLETED)
                self.db_session.commit()

            except Exception:
                shutil.rmtree(temp_path, onerror=self.handleRemoveReadonly)
                logger.exception('Exception while creating %s requested by %s - job id = %s',
                                  new_tar_name, created_by, self.job_id)
                self.create_tar_job.set_status(JobStatus.FAILED)
                self.db_session.commit()

        finally:
            self.db_session.close()

    def handleRemoveReadonly(self, func, path, exc):
        excvalue = exc[1]
        if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
            os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
            func(path)
        else:
            raise

    def get_unique_key(self):
        return 'create_tar_job_{}'.format(self.job_id)

    def progress_listener(self, buff):
        if self.create_tar_job and self.db_session:
            #print len(buff)
            self.upload_progress += len(buff)
            new_status = 'Upload progress: {} bytes'.format(self.upload_progress)
            print new_status
            self.create_tar_job.set_status(new_status)
            self.db_session.commit()
            #print self.create_tar_job.new_tar_name
            #print self.upload_progress
        else:
            print "not create_tar_job or not db_session"
