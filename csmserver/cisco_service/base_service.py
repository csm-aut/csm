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
import json
import requests

HTTP_ACCESS_TOKEN_URL = "https://cloudsso.cisco.com/as/token.oauth2"
BSD_ACCESS_TOKEN = "access_token"


class BaseServiceHandler(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    @classmethod
    def get_access_token(cls, username, password, client_id, client_secret):
        payload = {'client_id': client_id, 'client_secret': client_secret,
                   'username': username, 'password': password, 'grant_type': 'password'}
        response = requests.post(HTTP_ACCESS_TOKEN_URL, params=payload)
        return json.loads(response.text)[BSD_ACCESS_TOKEN]

    def debug_print(self, heading, data):
        print(heading, data)

    def get_json_value(self, json_object, key):
        if isinstance(json_object, dict):
            for k, v in json_object.items():
                if k == key:
                    return v
                value = self.get_json_value(v, key)
                if value is not None:
                    return value
        elif isinstance(json_object, list):
            for v in json_object:
                value = self.get_json_value(v, key)
                if value is not None:
                    return value
        else:
            return None