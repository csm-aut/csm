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
from utils import concatenate_dirs

from models import logger

try:
    import pysftp
    SFTP_SUPPORTED = True
except Exception:
    SFTP_SUPPORTED = False

try:
    # https://pypi.python.org/pypi/scp
    import paramiko
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

    def get_hostname(self):
        """
        support non-default port.  server_url is in the form of <server address>:<port>
        """
        if ':' in self.server.server_url:
            return self.server.server_url.split(':')[0]
        return self.server.server_url

    def get_port(self):
        """
        support non-default port.  server_url is in the form of <server address>:<port>
        """
        if ':' in self.server.server_url:
            return int(self.server.server_url.split(':')[1])
        return int(self.get_default_port())

    def get_default_port(self):
        raise NotImplementedError("Children must override get_default_port()")

    def get_file_and_directory_dict(self, sub_directory=None):
        raise NotImplementedError("Children must override get_file_and_directory_dict()")
    
    def check_reachability(self):
        raise NotImplementedError("Children must override check_reachability()")

    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):
        """
        Upload file to the designated server repository.
        source_file_path - complete path to the source file
        dest_filename - filename on the server repository
        sub_directory - sub-directory under the server repository
        """
        raise NotImplementedError("Children must override upload_file")


class TFTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def get_file_and_directory_dict(self, sub_directory=None):
        """
        Return an array of dictionaries: {'filename': [file|directory]', is_directory: [False|True]}
        """
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

        destination_file_path = os.path.join(path, dest_filename)
        try:
            shutil.copy(source_file_path, destination_file_path)
        except shutil.Error:
            logger.exception('upload_file() hit exception - source: {}, destination: {}.'.format(source_file_path,
                                                                                                 destination_file_path))
        
class FTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def get_default_port(self):
        return 21

    def get_file_and_directory_dict(self, sub_directory=None):
        result_list = []
        is_reachable = False

        try:
            ftp = self.get_connection(concatenate_dirs(self.server.server_directory, sub_directory))
            file_listing = []
            ftp.retrlines('LIST', file_listing.append)
            result_list = parse_unix_file_listing(file_listing=file_listing, sub_directory=sub_directory)

            is_reachable = True
        except Exception as e:
            logger.exception('FTP Server hit exception - {}'.format(e.message))
 
        return result_list, is_reachable
    
    def check_reachability(self):
        error = None
        is_reachable = False

        try:
            self.get_connection(self.server.server_directory)
            is_reachable = True
        except Exception as e:
            logger.exception('FTP Server hit exception - {}'.format(e.message))
            error = e.strerror if is_empty(e.message) else e.message

        return is_reachable, error
        
    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):
        with open(source_file_path, 'rb') as file:
            ftp = self.get_connection(concatenate_dirs(self.server.server_directory, sub_directory))

            # default block size is 8912
            if callback:
                ftp.storbinary('STOR ' + dest_filename, file, callback=callback)
            else:
                ftp.storbinary('STOR ' + dest_filename, file)
            ftp.quit()

    def get_connection(self, remote_directory=None):
        if not ping_test(self.get_hostname()):
            raise Exception('The host is not reachable.')

        ftp = ftplib.FTP()
        ftp.connect(self.get_hostname(), self.get_port())
        ftp.login(self.server.username, self.server.password)

        if remote_directory and len(remote_directory) > 0:
            ftp.cwd(remote_directory)

        return ftp


class SFTPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def get_default_port(self):
        return 22

    def get_connection_info(self):
        return {'host': self.get_hostname(), 'username': self.server.username,
                'password': self.server.password, 'port': self.get_port()}

    def get_file_and_directory_dict(self, sub_directory=None):
        result_list = []
        is_reachable = False

        if SFTP_SUPPORTED:
            try:
                with self.get_connection(concatenate_dirs(self.server.server_directory, sub_directory)) as sftp:
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
                logger.exception('SFTP Server hit exception - {}'.format(e.message))

        return result_list, is_reachable
    
    def check_reachability(self):
        error = None
        is_reachable = False

        if not SFTP_SUPPORTED:
            error = 'SFTP supported libraries have not been installed.'
        else:
            try:
                with self.get_connection(self.server.server_directory):
                    is_reachable = True
            except Exception as e:
                logger.exception('SFTP Server hit exception - {}'.format(e.message))
                error = e.strerror if is_empty(e.message) else e.message

        return is_reachable, error
        
    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):
        if SFTP_SUPPORTED:
            with self.get_connection(concatenate_dirs(self.server.server_directory, sub_directory)) as sftp:
                if callback:
                    sftp.put(source_file_path, remotepath=dest_filename, callback=callback)
                else:
                    sftp.put(source_file_path, remotepath=dest_filename)

    def get_connection(self, remote_directory=None):
        if not ping_test(self.get_hostname()):
            raise Exception('The host is not reachable.')

        sftp = pysftp.Connection(**self.get_connection_info())
        if remote_directory and len(remote_directory) > 0:
            sftp.chdir(remote_directory)

        return sftp


class SCPServer(ServerImpl):
    def __init__(self, server):
        ServerImpl.__init__(self, server)

    def get_default_port(self):
        return 22

    def get_file_and_directory_dict(self, sub_directory=None):
        result_list = []
        is_reachable = False

        if not SCP_SUPPORTED:
            return result_list, is_reachable

        try:
            remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)
            with self.get_connection(remote_directory) as ssh:
                stdin, stdout, stderr = ssh.exec_command('cd {};ls -l'.format(remote_directory))
                result_list = parse_unix_file_listing(file_listing=stdout.read().splitlines(),
                                                      sub_directory=sub_directory)
            is_reachable = True
        except Exception as e:
            logger.exception('SCP Server hit exception - {}'.format(e.message))

        return result_list, is_reachable

    def check_reachability(self):
        error = None
        is_reachable = False

        if not SCP_SUPPORTED:
            error = 'SCP supported libraries have not been installed.'
        else:
            try:
                with self.get_connection(self.server.server_directory):
                    is_reachable = True
            except Exception as e:
                logger.exception('SCP Server hit exception - {}'.format(e.message))
                error = e.strerror if is_empty(e.message) else e.message

        return is_reachable, error

    def upload_file(self, source_file_path, dest_filename, sub_directory=None, callback=None):

        try:
            ssh = self.get_connection()
            remote_directory = concatenate_dirs(self.server.server_directory, sub_directory)

            with SCPClient(ssh.get_transport(), socket_timeout=15.0) as scp:
                scp.put(source_file_path, os.path.join(remote_directory, dest_filename))

        except Exception as e:
            logger.exception('SCP Server hit exception - %s' % e.message)

    def get_connection(self, remote_directory=None):
        if not ping_test(self.get_hostname()):
            raise Exception('The host is not reachable.')

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.load_system_host_keys()

        ssh.connect(hostname=self.get_hostname(), port=self.get_port(),
                    username=self.server.username, password=self.server.password)

        if remote_directory and len(remote_directory) > 0:
            sftp = ssh.open_sftp()
            sftp.chdir(remote_directory)

        return ssh


def parse_unix_file_listing(file_listing, sub_directory=None):
    """
    List the contents of the FTP object's cwd and return two tuples of

       (filename, size, mtime, mode, link)

    one for subdirectories, and one for non-directories (normal files and other
    stuff).  If the path is a symbolic link, 'link' is set to the target of the
    link (note that both files and directories can be symbolic links).

    Note: we only parse Linux/UNIX style listings; this could easily be extended.

    -rw-r--r--    1 root     root      4749556 Nov  9  2015 file1
    drw-r--r--    1 root     root       253272 Sep 26  2016 directory1
    """
    _calmonths = dict((x, i + 1) for i, x in
    enumerate(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')))

    dirs, nondirs = [], []

    for line in file_listing:
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

    result_list = []
    for file_tuple in nondirs:
        result_list.append({'filename': file_tuple[0], 'is_directory': False})

    for file_tuple in dirs:
        if sub_directory is None or len(sub_directory) == 0:
            result_list.append({'filename': file_tuple[0], 'is_directory': True})
        else:
            result_list.append({'filename': os.path.join(sub_directory, file_tuple[0]), 'is_directory': True})

    return result_list


def ping_test(ip_address):
    try:
        return True if os.system("ping -c 1 " + ip_address) is 0 else False
    except Exception:
        return False