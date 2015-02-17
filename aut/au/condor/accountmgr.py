# =============================================================================
# accountmgr.py
#
# Copyright (c)  2014, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
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

import ConfigParser
import getpass
import fnmatch

try:
    import keyring
except:
    pass


def make_realm(name):
    return "Accelerated Upgrade@{}".format(name)

class AccountManager(object):
    def __init__(self,
                 config_file='accounts.cfg',
                 username_cb=None,
                 password_cb=None,
        ):
        self.config_file = config_file
        self.config = ConfigParser.SafeConfigParser({
                'username':'',
                })
        self.config.read(self.config_file)
        self.config.write(open(self.config_file, 'w'))

        self.username_cb = username_cb \
            if callable(username_cb) else self._prompt_for_username
        self.password_cb = password_cb \
            if callable(password_cb) else self._prompt_for_password

    def _prompt_for_username(self, prompt):
        # Not sure needed
        return None

    def _prompt_for_password(self, prompt):
        return getpass.getpass(prompt)

    def _find_section(self, realm):
        for section in iter(self.config.sections()):
            if fnmatch.fnmatch(realm, section):
                break
        else:
            section = 'DEFAULT'
        return section

    def _get_username(self, section):
        username = self.config.get(section, 'username')
        if username == '':
            return None
        return username

    def get_username(self, realm):
        username = self._get_username(self._find_section(realm))
        if not username:
            username = getpass.getuser()
        return username

    def get_password(self, realm, username=None, interact=True):
        section = self._find_section(realm)
        config_user_name = self._get_username(section)
        if not config_user_name or username != config_user_name:
                return None

        if not username:
            username = config_user_name

        try:
            password = keyring.get_password(make_realm(section), username)
        except:
            password = None

        if password == None and interact:
            prompt = "{}@{} Password: ".format(username, realm)
            password = self.password_cb(prompt)
            self.set_password(
                make_realm(section),
                username,
                password)

        #config.set(device_name, 'username', username)
        #config.write(open(self.config_file, 'w'))
        return password

    def set_password(self, realm, username, password):
        try:
            keyring.set_password(
                realm,
                username,
                password
            )
        except:
            pass

    def get_login(self, realm):
        username = self.get_username(realm)
        password = self.get_password(realm, username)
        return (username, password)
