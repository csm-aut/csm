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
import os
import sys
import datetime, time
import re
import ftplib
import shutil

from constants import ServerType

from utils import is_empty
from utils import get_file_list
from utils import concatenate_dirs

from models import logger

try:
    import pysftp
    SFTP_SUPPORTED = True
except Exception:
    SFTP_SUPPORTED = False

try:
    from paramiko import SSHClient
    from scp import SCPClient
    SCP_SUPPORTED = True
except Exception:
    SCP_SUPPORTED = False


def get_server_impl(server):
    if server.server_type == ServerType.TFTP_SERVER:
        return TFTPServer(server) 
    elif server.server_type == ServerType.FTP_SERVER:
        return FTPServer(server)
    elif server.server_type == ServerType.SFTP_SERVER:
        return SFTPServer(server)
    elif server.server_type == ServerType.SCP_SERVER:
        return SCPServer(server)
    else:
        return None


class ServerImpl(object):
    def __init__(self, server):
        self.server = server
        
    def get_file_list(self):
        raise NotImplementedError("Children must override get_file_list")
    
    def get_file_and_directory_dict(self, sub_directory=None):
        raise NotImplementedError("Children must override get_file_list")
    
    def check_reachability(self):
        raise NotImplementedError("Children must override check_reachability")
    
    """
    Upload file to the designated server repository.
    source_file_path - complete path to the source file
    dest_filename - filename on the server repository
    sub_directory - sub-directory under the server repository
    """
    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):
        raise NotImplementedError("Children must override upload_file")


class TFTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def get_file_list(self):
        return get_file_list(self.server.server_directory)
    
    """
    Return an array of dictionaries: {'filename': [file|directory]', is_directory: [False|True]}
    """
    def get_file_and_directory_dict(self, sub_directory=None): 
        result_list = []
        is_reachable = False

        if is_empty(sub_directory):
            path = self.server.server_directory
        else:
            path = os.path.join(self.server.server_directory, sub_directory)

        if os.path.exists(path):
            for name in os.listdir(path):
                file = dict()

                if os.path.isfile(os.path.join(path, name)):
                    file['filename'] = name
                    file['is_directory'] = False
                else:
                    file['filename'] = name if is_empty(sub_directory) else (sub_directory + os.sep + name)
                    file['is_directory'] = True

                result_list.append(file)

            is_reachable = True

        return result_list, is_reachable

    def check_reachability(self):
        error = None
        is_reachable = False

        if os.path.isdir(self.server.server_directory):
            is_reachable = True
        else:
            error = '{} is not a directory'.format(self.server.server_directory)

        return is_reachable, error
        
    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):
        if sub_directory is None:
            path = self.server.server_directory
        else:
            path = os.path.join(self.server.server_directory, sub_directory)
            
        shutil.copy(source_file_path, os.path.join(path, dest_filename))
            
        
class FTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def listdir(self, ftp):
        _calmonths = dict((x, i + 1) for i, x in
                   enumerate(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')))
        """
        List the contents of the FTP object's cwd and return two tuples of

           (filename, size, mtime, mode, link)

        one for subdirectories, and one for non-directories (normal files and other
        stuff).  If the path is a symbolic link, 'link' is set to the target of the
        link (note that both files and directories can be symbolic links).

        Note: we only parse Linux/UNIX style listings; this could easily be
        extended.
        """
        dirs, nondirs = [], []
        listing = []
        ftp.retrlines('LIST', listing.append)
        for line in listing:
            # Parse, assuming a UNIX listing
            words = line.split(None, 8)
            if len(words) < 6:
                print >> sys.stderr, 'Warning: Error reading short line', line
                continue

            # Get the filename.
            filename = words[-1].lstrip()
            if filename in ('.', '..'):
                continue

            # Get the link target, if the file is a symlink.
            extra = None
            i = filename.find(" -> ")
            if i >= 0:
                # words[0] had better start with 'l'...
                extra = filename[i + 4:]
                filename = filename[:i]

            # Get the file size.
            size = int(words[4])

            # Get the date.
            year = datetime.datetime.today().year
            month = _calmonths[words[5]]
            day = int(words[6])
            mo = re.match('(\d+):(\d+)', words[7])
            if mo:
                hour, min = map(int, mo.groups())
            else:
                mo = re.match('(\d\d\d\d)', words[7])
                if mo:
                    year = int(mo.group(1))
                    hour, min = 0, 0
                else:
                    raise ValueError("Could not parse time/year in line: '%s'" % line)
            dt = datetime.datetime(year, month, day, hour, min)
            mtime = time.mktime(dt.timetuple())

            # Get the type and mode.
            mode = words[0]

            entry = (filename, size, mtime, mode, extra)
            if mode[0] == 'd':
                dirs.append(entry)
            else:
                nondirs.append(entry)
        return dirs, nondirs

    def get_file_list(self):
        result_list = []
        is_reachable = False
        try:
            ftp = ftplib.FTP(self.server.server_url, user=self.server.username, passwd=self.server.password)

            if self.server.server_directory is not None and len(self.server.server_directory) > 0:
                ftp.cwd(self.server.server_directory)
            
            dirs, nondirs = self.listdir(ftp)
    
            if nondirs is not None:
                for file_tuple in nondirs:
                    result_list.append(file_tuple[0])

            is_reachable = True
        except Exception as e:
            logger.exception('FTPServer hit exception - ' + e.message)

        return result_list, is_reachable
    
    def get_file_and_directory_dict(self, sub_directory=None):
        result_list = []
        is_reachable = False
  
        try:
            ftp = ftplib.FTP(self.server.server_url, user=self.server.username, passwd=self.server.password)
                   
            remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
            if len(remote_directory) > 0:
                ftp.cwd(remote_directory)
            
            dirs, nondirs = self.listdir(ftp)
    
            for file_tuple in nondirs:
                result_list.append({'filename': file_tuple[0], 'is_directory': False})
                
            for file_tuple in dirs:
                if sub_directory is None or len(sub_directory) == 0:
                    result_list.append({'filename': file_tuple[0], 'is_directory': True})
                else:
                    result_list.append({'filename': os.path.join(sub_directory, file_tuple[0]), 'is_directory': True})

            is_reachable = True
        except Exception as e:
            logger.exception('FTPServer hit exception - ' + e.message)
 
        return result_list, is_reachable
    
    def check_reachability(self):
        error = None
        is_reachable = False

        try:
            ftp = ftplib.FTP(self.server.server_url, user=self.server.username, passwd=self.server.password)

            if not is_empty(self.server.server_directory):
                ftp.cwd(self.server.server_directory)
        
            is_reachable = True
        except Exception as e:
            error = e.message

        return is_reachable, error
        
    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):
        with open(source_file_path, 'rb') as file:
            
            ftp = ftplib.FTP(self.server.server_url, user=self.server.username, passwd=self.server.password)
                   
            remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
            if len(remote_directory) > 0:
                ftp.cwd(remote_directory)
                
            # default block size is 8912
            if callback:
                ftp.storbinary('STOR ' + dest_filename, file, callback=callback)
            else:
                ftp.storbinary('STOR ' + dest_filename, file)
            ftp.quit()

    def delete_file(self, filename, sub_directory=None, callback=None):
        ftp = ftplib.FTP(self.server.server_url, user=self.server.username, passwd=self.server.password)

        remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
        if len(remote_directory) > 0:
            ftp.cwd(remote_directory)

        ftp.delete(filename)

    def handler(self, block):
        pass


class SFTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)
    
    def get_file_list(self):
        result_list = []
        is_reachable = False

        if not SFTP_SUPPORTED:
            return result_list, is_reachable
        
        try:
            server = self.server
            with pysftp.Connection(server.server_url, username=server.username, password=server.password) as sftp:
                if server.server_directory is not None and len(server.server_directory) > 0:
                    sftp.chdir(server.server_directory)

                result_list = sftp.listdir()

            is_reachable = True
        except Exception as e:
            logger.exception('SFTPServer hit exception - ' + e.message)
                   
        return result_list, is_reachable

    def get_file_and_directory_dict(self, sub_directory=None):
        result_list = []
        is_reachable = False

        if not SFTP_SUPPORTED:
            return result_list, is_reachable
        
        try:
            with pysftp.Connection(self.server.server_url, username=self.server.username, password=self.server.password) as sftp:
                remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
                if len(remote_directory) > 0:
                    sftp.chdir(remote_directory)

                file_info_list = sftp.listdir()
                for file_info in file_info_list:
                    file = {}
                    lstatout = str(sftp.lstat(file_info)).split()[0]

                    if 'd' in lstatout:
                        if sub_directory is None or len(sub_directory) == 0:
                            file['filename'] = file_info
                        else:
                            file['filename'] = sub_directory + '/' + file_info
                        file['is_directory'] = True
                    else:
                        file['filename'] = file_info
                        file['is_directory'] = False

                    result_list.append(file)

            is_reachable = True
        except Exception as e:
            logger.exception('SFTPServer hit exception - ' + e.message)
            
        return result_list, is_reachable
    
    def check_reachability(self):
        error = None
        is_reachable = False

        if not SFTP_SUPPORTED:
            error = 'SFTP supported libraries have not been installed.'
        else:
            try:
                with pysftp.Connection(self.server.server_url, username=self.server.username, password=self.server.password) as sftp:
                    if not is_empty(self.server.server_directory):
                        sftp.chdir(self.server.server_directory)

                is_reachable = True

            except Exception as e:
                error = e.strerror if is_empty(e.message) else e.message
                logger.exception('SFTPServer hit exception - ' + error)

        return is_reachable, error
        
    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):
        if SFTP_SUPPORTED:
            with pysftp.Connection(self.server.server_url, username=self.server.username, password=self.server.password) as sftp:
                remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
                if len(remote_directory) > 0:
                    sftp.chdir(remote_directory)

                if callback:
                    sftp.put(source_file_path, remotepath=dest_filename, callback=callback)
                else:
                    sftp.put(source_file_path, remotepath=dest_filename)


class SCPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def get_file_list(self):
        return self.get_file_and_directory_dict()

    def get_file_and_directory_dict(self, sub_directory=None):
        is_reachable, error = self.check_reachability()
        return [], is_reachable

    def check_reachability(self):
        if not SCP_SUPPORTED:
            # https://pypi.python.org/pypi/scp
            error = 'SCP supported libraries have not been installed.'
            return False, error

        try:
            ssh = SSHClient()
            ssh.load_system_host_keys()
            ssh.connect(self.server.server_url, username=self.server.username, password=self.server.password)
        except Exception as e:
            logger.exception('SCPServer hit exception - %s' % e.message)
            return False, e.message

        return True, None

    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):
        try:
            ssh = SSHClient()
            ssh.load_system_host_keys()
            ssh.connect(self.server.server_url, username=self.server.username, password=self.server.password)

            with SCPClient(ssh.get_transport(), socket_timeout=15.0) as scp:
                scp.put(source_file_path, os.path.join(self.server.server_directory, dest_filename))

        except Exception as e:
            logger.exception('SCPServer hit exception - %s' % e.message)


