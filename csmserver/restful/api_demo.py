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

"""
To run this demo as a standalone, you will need to install 'requests'.
For example, pip install requests
"""
import requests
import json
import ast

BASE_URL = "http://localhost:5000/api/v1/"
token = ''


def get_token():
    global token

    username = raw_input("\nUsername: ")
    password = raw_input("Password: ")

    url = BASE_URL + "token"
    print "URL: " + url

    resp = requests.get(url, auth=(username, password))
    if resp.status_code == 200:
        token = ast.literal_eval(resp.content).get('token')
    else:
        token = resp.text

    print 'token: ', token


def print_response(response):
    try:
        outputs = json.dumps(response.json(), indent=2)
    except ValueError:
        outputs = response.text

    print 'Status Code:', response.status_code
    print outputs


def build_url(part):
    print
    url = BASE_URL + part
    print 'URL: ' + url
    return url


def get_hosts():
    resp = requests.get(build_url('hosts?page=1'), auth=(token, 'unused'))
    print_response(resp)


def create_hosts():
    payload = [
        {'hostname': 'My Host 1', 'region': 'RTP-SVS', 'roles': 'PE', 'connection_type': 'telnet',
         'host_or_ip': '172.28.98.2', 'username': 'cisco', 'password': 'cisco'},

        {'hostname': 'My Host 2', 'region': 'SJ Labs', 'roles': 'PE', 'connection_type': 'telnet',
         'host_or_ip': '172.28.98.2', 'username': 'cisco', 'password': 'cisco'},
    ]
    resp = requests.post(build_url('hosts'), auth=(token, 'unused'), json=payload)
    print_response(resp)


def delete_host(hostname):
    """
    http://localhost:5000/api/v1/hosts/<hostname>/delete
    """
    resp = requests.delete(build_url('hosts/' + hostname + '/delete'), auth=(token, 'unused'))
    print_response(resp)


def display_choices():
    print
    print('1. Get Token')
    print('2. Create Hosts')
    print('3. Get Hosts')
    print('4. Delete Host')
    print


def main():
    display_choices()

    while raw_input("Would you like to continue (Y/N)? ") not in ['N','n']:
        choice = raw_input("Enter selection ")
        if choice == '1':
            get_token()
        elif choice == '2':
            create_hosts()
        elif choice == '3':
            get_hosts()
        elif choice == '4':
            delete_host('My Host 2')

        display_choices()

if __name__ == "__main__":
    main()
