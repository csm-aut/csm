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
import os
import sys
import datetime, time
import re
import ftplib
import shutil

from constants import ServerType
from utils import get_file_list
from utils import import_module
from utils import concatenate_dirs
from models import logger

def get_server_impl(server):
    if server.server_type == ServerType.TFTP_SERVER:
        return TFTPServer(server) 
    elif server.server_type == ServerType.FTP_SERVER:
        return FTPServer(server)
    elif server.server_type == ServerType.SFTP_SERVER:
        return SFTPServer(server)
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
    def upload_file(self, source_file_path, dest_filename, sub_directory=None):
        raise NotImplementedError("Children must override upload_file")
    
class TFTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def get_file_list(self):
        return get_file_list(self.server.server_directory)
    
    """
    Return an array of dictionaries: {'filename': [file|directory]', is_directory: [False/True]}
    """
    def get_file_and_directory_dict(self, sub_directory=None): 
        result_list = []
        is_reachable = True
        
        try:
            if sub_directory is None:
                path = self.server.server_directory
            else:
                path = (self.server.server_directory + os.sep + sub_directory)
 
            for name in os.listdir(path):
                file = {}            
 
                if os.path.isfile(os.path.join(path, name)):
                    file['filename'] = name
                    file['is_directory'] = False
                else:
                    if sub_directory is None or len(sub_directory) == 0:
                        file['filename'] = name
                    else:
                        file['filename'] = sub_directory + '/' + name
                    file['is_directory'] = True
            
                result_list.append(file)
        except:
            is_reachable = False
              
        return result_list, is_reachable
    
    
    def check_reachability(self):
        try:
            if os.path.isdir(self.server.server_directory):
                return True
        
            return False
        except:
            return False
        
    def upload_file(self, source_file_path, dest_filename, sub_directory=None):
        if sub_directory is None:
            path = self.server.server_directory
        else:
            path = (self.server.server_directory + os.sep + sub_directory)
            
        shutil.copy(source_file_path, path + os.sep + dest_filename)
            
        
class FTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def listdir(self, ftp):
        _calmonths = dict((x, i + 1) for i, x in
                   enumerate(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')))
        """
        List the contents of the FTP opbject's cwd and return two tuples of

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
        is_reachable = True
        try:
            ftp = ftplib.FTP(self.server.server_url, user=self.server.username, passwd=self.server.password)

            if self.server.server_directory is not None and len(self.server.server_directory) > 0:
                ftp.cwd(self.server.server_directory)
            
            dirs, nondirs = self.listdir(ftp)
    
            if nondirs is not None:
                for file_tuple in nondirs:
                    result_list.append(file_tuple[0])
        except:
            logger.exception('FTPServer hit exception') 
            is_reachable = False

        return result_list, is_reachable
    
    def get_file_and_directory_dict(self, sub_directory=None):
        result_list = []
        is_reachable = True
  
        try:
            ftp = ftplib.FTP(self.server.server_url, user=self.server.username, passwd=self.server.password)
                   
            remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
            if len(remote_directory) > 0:
                ftp.cwd(remote_directory)
            
            dirs, nondirs = self.listdir(ftp)
    
            for file_tuple in nondirs:
                result_list.append({'filename':file_tuple[0], 'is_directory':False})
                
            for file_tuple in dirs:
                if sub_directory is None or len(sub_directory) == 0:
                    result_list.append({'filename':file_tuple[0], 'is_directory':True})
                else:
                    result_list.append({'filename':sub_directory + '/' + file_tuple[0], 'is_directory':True})
        except:
            logger.exception('FTPServer hit exception') 
            is_reachable = False
 
        return result_list, is_reachable
    
    def check_reachability(self):
        try:
            server = self.server
            ftp = ftplib.FTP(server.server_url, user=server.username, passwd=server.password)

            if server.server_directory is not None and len(server.server_directory) > 0:
                ftp.cwd(server.server_directory)
        
            return True
        except:
            return False
        
    def upload_file(self, source_file_path, dest_filename, sub_directory=None):
        try:
            file = open(source_file_path, 'rb')
            
            ftp = ftplib.FTP(self.server.server_url, user=self.server.username, passwd=self.server.password)
                   
            remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
            if len(remote_directory) > 0:
                ftp.cwd(remote_directory)
                
            # default block size is 8912
            ftp.storbinary('STOR ' + dest_filename, file, callback=self.handler)
            ftp.quit()    
            file.close()

        finally:
            if file is not None:
                file.close()
            
    def handler(self, block):
        pass
        
class SFTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)
    
    def get_file_list(self):
        result_list = []
        is_reachable = True
        
        try:
            sftp_module = import_module('pysftp')
            if sftp_module is not None:
                server = self.server
                with sftp_module.Connection(server.server_url, username=server.username, password=server.password) as sftp:
                    if server.server_directory is not None and len(server.server_directory) > 0:
                        sftp.chdir(server.server_directory)
        
                    result_list = sftp.listdir()
        except:
            logger.exception('SFTPServer hit exception')
            is_reachable = False
                   
        return result_list, is_reachable

    def get_file_and_directory_dict(self, sub_directory=None):
        result_list = []
        is_reachable = True
        
        try:
            sftp_module = import_module('pysftp')
            if sftp_module is not None:
                with sftp_module.Connection(self.server.server_url, username=self.server.username, password=self.server.password) as sftp:
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
        except:
            logger.exception('SFTPServer hit exception')
            is_reachable = False
            
        return result_list, is_reachable
    
    def check_reachability(self):
        try:
            sftp_module = import_module('pysftp')
            if sftp_module is not None:
                server = self.server
                with sftp_module.Connection(server.server_url, username=server.username, password=server.password) as sftp:
                    if server.server_directory is not None and len(server.server_directory) > 0:
                        sftp.chdir(server.server_directory)      
                return True
            else:
                return False
        except:
            return False
        
    def upload_file(self, source_file_path, dest_filename, sub_directory=None):
        sftp_module = import_module('pysftp')

        with sftp_module.Connection(self.server.server_url, username=self.server.username, password=self.server.password) as sftp:
            remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
            if len(remote_directory) > 0:
                sftp.chdir(remote_directory)
            sftp.put(source_file_path) 
            
        
if __name__ == '__main__':         
    pass
    
