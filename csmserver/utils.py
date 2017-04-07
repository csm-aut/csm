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
from urlparse import urlparse
from constants import PlatformFamily

import re
import sys
import os
import stat
import time
import datetime 
import importlib
import tarfile
import urllib
import re

from constants import get_log_directory, get_temp_directory
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


def create_log_directory(host_or_ip, id=None):
    job_id = (('-' + str(id)) if id else "")
    host_ip = host_or_ip.strip().replace('.', '_').replace(' ', '_')
    date_string = datetime.datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")
    directory = get_log_directory() + host_ip + '-' + date_string + job_id

    if not path.exists(directory):
        makedirs(directory)

    return host_ip + '-' + date_string + job_id


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


def get_datetime(date_string, format=None):
    """
    Converts a datetime string to internal python datetime.
    Returns None if the string is not a valid date time.
    """
    try:
        if not format:
            # 2016-12-12 13:07:32
            match = re.search('\d+-\d+-\d+ \d+:\d+:\d+', date_string)
            if match:
                format = '%Y-%m-%d %H:%M:%S'
            else:
                # 01/17/2017 11:10 PM
                match = re.search('\d+/\d+/\d+ \d+:\d+ [A|P]M', date_string)
                if match:
                    format = "%m/%d/%Y %I:%M %p"

        return datetime.datetime.strptime(date_string, format)
    except:
        return None


def multiple_replace(string, rep_dict):
    """
    Performs a one-pass replacements
    """
    pattern = re.compile("|".join([re.escape(k) for k in rep_dict.keys()]), re.M)
    return pattern.sub(lambda x: rep_dict[x.group(0)], string)


def get_datetime_string(datetime, format):
    try:
        return datetime.strftime(format)
    except:
        return None    


def datetime_from_local_to_utc(local_datetime):
    """
    :param local_datetime: Python datetime object
    :return: UTC datetime string
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.mktime(local_datetime.timetuple())))


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


def get_file_timestamp(file_path):
    t = os.path.getmtime(file_path)
    return datetime.datetime.fromtimestamp(t)


def make_url(connection_type, host_username, host_password, host_or_ip, port_number, enable_password=None):
    """
    Creates a connection URL such as

    telnet://user:pass@1.1.1.1 (without port)
    telnet://user:pass@1.1.1.1:2048 (with port)
    telnet://:pass@1.1.1.1:2048 (empty user)
    telnet://user:@1.1.1.1:2048 (empty password)
    telnet://user@1.1.1.1:2048 (no password)
    telnet://:@1.1.1.1:2048 (empty user and password)
    telnet://1.1.1.1:2048 (no user and password)
    telnet://user:pass@1.1.1.1:2048/enable password (with enable password)

    """
    url = '{}://'.format(connection_type)

    no_host_username = False
    no_host_password = False

    if not is_empty(host_username):
        url += '{}'.format(urllib.quote(host_username, safe=""))
    else:
        no_host_username = True

    if not is_empty(host_password):
        url += ':{}'.format(urllib.quote(host_password, safe=""))
    else:
        no_host_password = True

    if no_host_username and no_host_password:
        url += '{}'.format(host_or_ip)
    else:
        url += '@{}'.format(host_or_ip)

    if not is_empty(port_number):
        url += ':{}'.format(port_number)

    if not is_empty(enable_password):
        url += '?enable_password={}'.format(urllib.quote(enable_password, safe=""))

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
            result_dir = os.path.join(result_dir, dir2)
    
    return result_dir


def get_base_url(url):
    """
    Returns the base URL including the port number
    e.g. (http://localhost:5000)
    """
    parsed = urlparse(url)
    base_url = "{}://{}".format(parsed.scheme, parsed.hostname)
    if parsed.port is not None:
        base_url += ":{}".format(parsed.port)

    return base_url


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
    if input_string is not None:
        temp = re.sub("[^a-z0-9()-_.\s]", '', input_string, flags=re.I)
        return re.sub("\s+", " ", temp).strip()
    else:
        return None


def check_acceptable_string(input_string):
    """ Will throw exception if the result string is blank or None. """
    orig_input_string = input_string
    input_string = get_acceptable_string(input_string)
    if input_string is None or len(input_string) == 0:
        raise ValueError('"' + orig_input_string +
                         '" contains invalid characters. It should only contain a-z, A-Z, 0-9, (). -_')
    return input_string


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

    return dmp.diff_prettyHtml(diff)


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


def get_json_value(json_object, key):
    if isinstance(json_object, dict):
        for k, v in json_object.items():
            if k == key:
                return v
            value = get_json_value(v, key)
            if value is not None:
                return value
    elif isinstance(json_object, list):
        for v in json_object:
            value = get_json_value(v, key)
            if value is not None:
                return value
    else:
        return None


def create_temp_user_directory(username):
    if not os.path.isdir(os.path.join(get_temp_directory(), username)):
        os.makedirs(os.path.join(get_temp_directory(), username))
        make_file_writable(os.path.join(get_temp_directory(), username))

    return os.path.join(get_temp_directory(), username)


def get_software_platform(family, os_type):
    if family == PlatformFamily.ASR9K and os_type == 'eXR':
        return PlatformFamily.ASR9K_64
    else:
        return family


def get_software_version(version):
    # Strip all characters after '[' (i.e., 5.3.2[Default])
    head, sep, tail = version.partition('[')
    return head


def get_return_url(request, default_url=None):
    """
    Returns the return_url encoded in the parameters
    """
    url = request.args.get('return_url')
    if url is None:
        url = default_url
    return url


def create_list(arg):
    return arg if type(arg) is list else [arg]


def get_build_date():
    try:
        return open('build_date', 'r').read()
    except:
        pass

    return None


def get_config_value(config_file, section, key):
    module = import_module('ConfigParser')
    if module is None:
        module = import_module('configparser')

    config = module.RawConfigParser()
    config.read(config_file)

    if not config.has_section(section):
        return None
    else:
        section_dict = dict(config.items(section))
        if key in section_dict.keys():
            return section_dict[key]
        else:
            return None


def replace_multiple(text, dictionary):
    return reduce(lambda a, kv: a.replace(*kv), dictionary.iteritems(), text)

if __name__ == '__main__':
    print(get_acceptable_string('john SMITH~!@#$%^&*()_+().smith'))

