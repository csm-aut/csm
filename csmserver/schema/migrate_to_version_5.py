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
from schema.base import BaseMigrate
from database import DBSession
from models import Host
from models import HostContext

sql_statements = [
    'alter table system_option add enable_user_credential_for_host BOOLEAN default 0',
    'alter table user add host_password VARCHAR(100)',
    'alter table install_job add column custom_command_profile_id varchar(20)',
    'alter table host add family VARCHAR(20) default "Unknown"',
    'alter table host add os_type VARCHAR(20) default "Unknown"',
    'alter table system_option add default_host_authentication_choice VARCHAR(10) default "1"',
    'drop table device_udi',
    'alter table inventory_job change column pending_submit request_update BOOLEAN',
    ]

class SchemaMigrate(BaseMigrate):
    def __init__(self, version):
        BaseMigrate.__init__(self, version)

    def start(self):
        db_session = DBSession()
        for sql in sql_statements:
            try:
                db_session.execute(sql)
            except:
                pass

