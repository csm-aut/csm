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
from base_service import BaseServiceHandler

import requests

CLIENT_ID = "3rcz8pdxcbgrawp8eu3nw2nv"
CLIENT_SECRET = "HMVqGJDSmBM3tEAqnmc8hahJ"

HTTP_GET_BUG_INFO_URL = "https://api.cisco.com/bug/v2.0/bugs/bug_ids/"


class BugServiceHandler(BaseServiceHandler):
    def __init__(self, username, password, bug_id):
        BaseServiceHandler.__init__(self, username, password)

        self.bug_id = bug_id

    def get_bug_info(self):
        access_token = self.get_access_token(self.username, self.password)

        url_string = HTTP_GET_BUG_INFO_URL + self.bug_id
        headers = {'Authorization': 'Bearer ' + access_token}
        return requests.get(url_string, headers=headers).json()

    @classmethod
    def get_access_token(cls, username, password):
        return BaseServiceHandler.get_access_token(username, password, CLIENT_ID, CLIENT_SECRET)