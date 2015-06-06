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
from os import listdir, sep, path, makedirs
from os.path import isfile, join

import sys
import os
import stat
import datetime 
import importlib
import tarfile
import traceback

from constants import get_autlogs_directory

def import_class(cl):
    d = cl.rfind(".")
    classname = cl[d+1:len(cl)]
    m = __import__(cl[0:d], globals(), locals(), [classname])
    return getattr(m, classname)

def import_module(module, path=None):
    if path is not None:
        sys.path.append(path)
    try:
        return importlib.import_module(module)
    except:
        return None

def create_log_directory(host_or_ip, id):
    host = host_or_ip.strip().replace('.', '_').replace(' ','_')
    date_string = datetime.datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")
    directory = get_autlogs_directory() + host + '-' + date_string + '-' + str(id)

    if not path.exists(directory):
        makedirs(directory)
            
    return host + '-' + date_string + '-' + str(id)

def create_directory(directory):
    # Creates the a directory if not exist
    if not os.path.exists(directory):
        try:
            os.makedirs(directory) 
        except:
            print('ERROR: Unable to create directory' + directory)      
        
"""
Converts a datetime string to internal python datetime.  
Returns None if the string is not a valid date time.
"""
def get_datetime(date_string, format):
    try:
        return datetime.datetime.strptime(date_string, format)
    except:
        return None
    
def get_datetime_string(datetime, format):
    try:
        return datetime.strftime(format)
    except:
        return None    

def make_file_writable(file_path):
    if os.path.isfile(file_path):
        os.chmod(file_path, stat.S_IRWXU)  
        
def get_tarfile_file_list(tar_file_path):
    file_list = []
    
    tar = tarfile.open(tar_file_path)
    tar_info_list = tar.getmembers()
    for tar_info in tar_info_list:
        file_list.append(tar_info.name)
        
    return file_list

"""
Extract the tar file to a given output file directory and return the
content of the tar file as an array of filenames.
"""
def untar(tar_file_path, output_directory, remove_tar_file=None):
    file_list = []
    
    tar = tarfile.open(tar_file_path)
    tar_info_list = tar.getmembers()
    for tar_info in tar_info_list:
        file_list.append(tar_info.name)
        
    tar.extractall(output_directory)
    tar.close()
    
    # Modify the permission bit after files are extracted
    for filename in file_list:
        make_file_writable(output_directory + os.path.sep + filename)
            
    # Remove the tar file if indicated.
    if remove_tar_file:
        os.unlink(tar_file_path)
        
    return file_list


"""
Given a directory path, returns all files in that directory.
A filter may also be specified, for example, filter = '.pie'.
"""
def get_file_list(directory, filter=None):
    result_list = []

    try:
        file_list = [ f for f in listdir(directory) if isfile(join(directory,f)) ]
        for file in file_list:
            if filter is not None:
                if file.find(filter) != -1:
                    result_list.append(file) 
            else:
                result_list.append(file)
    except:
        pass

    return sorted(result_list)
    
"""
Creates a connection URL such as 

telnet://user:pass@1.1.1.1 (without port)
telnet://user:pass@1.1.1.1:2048 (with port)
telnet://:pass@1.1.1.1:2048 (empty user)
telnet://user:@1.1.1.1:2048 (empty password)
telnet://user@1.1.1.1:2048 (no password)
telnet://:@1.1.1.1:2048 (empty user and password)
telnet://1.1.1.1:2048 (no user and password)

"""
def make_url(connection_type, username, password, host_or_ip, port_number, default_username=None, default_password=None):
    url = '{}://'.format(connection_type)
    
    no_username = False
    no_password = False
    
    # Set the default username and password only if both username and password have not been specified
    if (username is None or len(username) == 0) and (password is None or len(password) == 0):
        if default_username is not None:
            username = default_username
        if default_password is not None:
            password = default_password
    
    if username is not None and len(username) > 0:
        url += '{}'.format(username)
    else:
        no_username = True
        
    if password is not None and len(password) > 0:
        url += ':{}'.format(password)
    else:
        no_password = True
           
    if no_username and no_password:
        url += '{}'.format(host_or_ip)
    else:
        url += '@{}'.format(host_or_ip)
    
    # It is possible there may be multiple ports separated by comma
    if port_number is not None and len(port_number) > 0:
        url += ':{}'.format(port_number) 
  
    return url

"""
Appends dir2 to dir1. It is possible that either/both dir1 or/and dir2 is/are None
"""
def concatenate_dirs(dir1, dir2):
    result_dir = dir1 if dir1 is not None and len(dir1) > 0 else ''
    if dir2 is not None and len(dir2) > 0:
        if len(result_dir) == 0:
            result_dir = dir2
        else:
            result_dir += '/' + dir2
    
    return result_dir

def trim_last_slash(str):
    if str is not None:
        if str.endswith('/'):
            return str[:-1]
    return str

"""
Returns the base URL including the port numbetr
e.g. (localhost:50000)
"""
def get_base_url(url):
    url = url.replace('http://', '')
    return 'http://' + url[:url.find('/')] 
    
def is_empty(obj):
    if obj is None or len(obj) == 0 or obj == 'None':
        return True
    else:
        return False
    
def comma_delimited_str_to_array(comma_delimited_str):
    if comma_delimited_str is None or len(comma_delimited_str) == 0:
        return []
    return comma_delimited_str.split(',')   

if __name__ == '__main__':
    pass
   
