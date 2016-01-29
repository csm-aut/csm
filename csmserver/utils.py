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
from os import listdir, sep, path, makedirs
from os.path import isfile, join
from diff_match_patch import diff_match_patch

import re
import sys
import os
import stat
import datetime 
import importlib
import tarfile
import re

from constants import get_log_directory
from __builtin__ import True


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
    host = host_or_ip.strip().replace('.', '_').replace(' ', '_')
    date_string = datetime.datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")
    directory = get_log_directory() + host + '-' + date_string + '-' + str(id)

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


def remove_extra_spaces(str):
    """
    Given a comma delimited string and remove extra spaces
    Example: 'x   x  ,   y,  z' becomes 'x x,y,z'
    """
    if str is not None:
        return ','.join([re.sub(r'\s+', ' ', x).strip() for x in str.split(',')])
    return str


def get_datetime(date_string, format):
    """
    Converts a datetime string to internal python datetime.
    Returns None if the string is not a valid date time.
    """
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
        os.chmod(file_path, stat.S_IRWXU|stat.S_IRWXG|stat.S_IRWXO)  


def get_tarfile_file_list(tar_file_path):
    file_list = []

    tar = tarfile.open(tar_file_path)
    tar_info_list = tar.getmembers()
    for tar_info in tar_info_list:
        file_list.append(tar_info.name)
        
    return file_list


def untar(tar_file_path, output_directory, remove_tar_file=None):
    """
    Extract the tar file to a given output file directory and return the
    content of the tar file as an array of filenames.
    """
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


def get_file_list(directory, filter=None):
    """
    Given a directory path, returns all files in that directory.
    A filter may also be specified, for example, filter = '.pie'.
    """
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


def make_url(connection_type, username, password, host_or_ip, port_number,
             default_username=None, default_password=None):
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
    url = '{}://'.format(connection_type)
    
    no_username = False
    no_password = False
    
    # Set the default username and password only if both username and password have not been specified
    if is_empty(username) and is_empty(password):
        if default_username is not None:
            username = default_username
        if default_password is not None:
            password = default_password
    
    if not is_empty(username):
        url += '{}'.format(username)
    else:
        no_username = True
        
    if not is_empty(password):
        url += ':{}'.format(password)
    else:
        no_password = True
           
    if no_username and no_password:
        url += '{}'.format(host_or_ip)
    else:
        url += '@{}'.format(host_or_ip)
    
    # It is possible there may be multiple ports separated by comma
    if not is_empty(port_number):
        url += ':{}'.format(port_number) 
  
    return url


def concatenate_dirs(dir1, dir2):
    """
    Appends dir2 to dir1. It is possible that either/both dir1 or/and dir2 is/are None
    """
    result_dir = dir1 if dir1 is not None and len(dir1) > 0 else ''
    if dir2 is not None and len(dir2) > 0:
        if len(result_dir) == 0:
            result_dir = dir2
        else:
            result_dir += '/' + dir2
    
    return result_dir


def trim_last_slash(s):
    if s is not None:
        if s.endswith('/'):
            return s[:-1]
    return s


def get_base_url(url):
    """
    Returns the base URL including the port numbetr
    e.g. (localhost:50000)
    """
    url = url.replace('http://', '')
    return 'http://' + url[:url.find('/')] 


def is_empty(obj):
    """
    These conditions are considered empty
       s = [], s = None, s = '', s = '    ', s = 'None'
    """
    if isinstance(obj, str):
        obj = obj.replace('None','').strip()

    if obj:
        return False

    return True


def get_acceptable_string(input_string):
    """
    Strips all unwanted characters except a-z, A-Z, 0-9, and '(). -_'
    """
    temp = re.sub("[^a-z0-9()-_.\s]",'', input_string, flags=re.I)
    return re.sub("\s+", " ", temp).strip()


def comma_delimited_str_to_list(comma_delimited_str):
    if is_empty(comma_delimited_str):
        return []
    return comma_delimited_str.split(',')   


def is_ldap_supported():
    try:
        import ldap
    except:
        return False
    return True


def generate_file_diff(filename1, filename2):
    """
    Given two files, return the file diff in HTML format.
    """
    text1 = ''
    text2 = ''

    try:
        with open(filename1) as f:
            text1 = f.read()
    except IOError:
        pass

    try:
        with open(filename2) as f:
            text2 = f.read()
    except IOError:
        pass

    dmp = diff_match_patch()
    diff = dmp.diff_main(text1, text2)

    dmp.diff_cleanupSemantic(diff)
    ds = dmp.diff_prettyHtml(diff)

    # Do some cleanup work here
    ds = ds.replace(' ', '&nbsp;')
    ds = ds.replace('ins&nbsp;style', 'ins style')
    ds = ds.replace('del&nbsp;style', 'del style')
    return ds


def generate_ip_range(start_ip, end_ip):
    """
    Given the start_ip and end_ip, generate all the IP addresses in between inclusively.
    Example, generate_ip_range("192.168.1.0", "192.168.2.0")
    """
    start = list(map(int, start_ip.split(".")))
    end = list(map(int, end_ip.split(".")))
    temp = start
    ip_range = []

    ip_range.append(start_ip)
    while temp != end:
        start[3] += 1
        for i in (3, 2, 1):
            if temp[i] == 256:
                temp[i] = 0
                temp[i - 1] += 1

        ip_range.append(".".join(map(str, temp)))

    return ip_range


if __name__ == '__main__':
    print(get_acceptable_string('john SMITH~!@#$%^&*()_+().smith'))
