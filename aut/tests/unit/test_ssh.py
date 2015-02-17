# =============================================================================
# test_ssh.py - Unit test cases using ssh
#
# Copyright (c) 2014, Cisco Systems
# All rights reserved.
#
# Author: Klaudiusz Staniek
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

from pexpect import pxssh
from pexpect import spawn

from au import accelerated_upgrade

import tests
from testtools.content import text_content
from au.lib.global_constants import *
from tests.fakes import asr_9k


class TestSSH(tests.TestCase):

    def login(self):
        accelerated_upgrade.term = 'ssh'
        accelerated_upgrade.verbose = True
        accelerated_upgrade.passwd = 's3cret'
        accelerated_upgrade.login = 'admin'
        ret, session = accelerated_upgrade.ssh_login(['1.1.1.1'])
        return ret, session

    def test_fake_ssh(self):
        ssh = pxssh.pxssh()
        ssh.login('server', 'me', password='s3cret')
        ssh.sendline('ping')
        ssh.expect('pong', timeout=10)
        assert ssh.prompt(timeout=10)
        ssh.logout()

    def test_ssh_login(self):
        ret, session = self.login()

        self.assertIsInstance(session, spawn)
        self.assertEqual(0, ret)

    def test_get_prompt(self):

        ret, session = self.login()

        prompt = accelerated_upgrade.get_prompt(session)
        self.assertEqual(prompt, session.prompt)

        search_window = len(prompt) + 1

        self.addDetail('prompt', text_content(prompt))

        session.sendline()
        status = session.expect_exact(
            [prompt], timeout=3, searchwindowsize=search_window)
        self.assertEqual(0, status)
        self.addDetail('first enter', text_content(session.before))

        session.sendline()
        status = session.expect_exact(
            [prompt], timeout=3, searchwindowsize=search_window)
        self.assertEqual(0, status)
        self.addDetail('second enter', text_content(session.before))

    def test_show_redundancy_summary(self):

        ret, session = self.login()
        prompt = accelerated_upgrade.get_prompt(session)
        search_window = len(prompt) + 1

        self.addDetail('prompt', text_content(prompt))

        session.sendline()
        status = session.expect_exact(
            [prompt], timeout=3, searchwindowsize=search_window)
        self.assertEqual(0, status)
        self.addDetail('received-prompt', text_content(session.after))

        cmd = 'show redundancy summary'
        session.sendline(cmd)

        status = session.expect_exact(
            [prompt, INVALID_INPUT, MORE, EOF],
            timeout=5,
            searchwindowsize=search_window
        )

        #check if get prompt after the command
        self.assertEqual(0, status)

        # replace LF with CR/LF (maybe different on Windows)
        output = asr_9k.commands[cmd][0].replace('\n', '\r\n')
        found = session.before.find(output)

        self.addDetail('found', text_content(str(found)))
        self.addDetail('received', text_content(session.before))
        self.addDetail('expected', text_content(output))

        self.assertNotEqual(-1, found)
