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
    'alter table smu_meta add tar_software_type_id VARCHAR(20)',
    'update smu_meta set `tar_software_type_id`="280805694"',
    'alter table smu_info modify id VARCHAR(100)',
    'alter table system_option add enable_ldap_host_auth BOOLEAN default 0'
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

        try:
            # Creates a context for existing hosts
            hosts = db_session.query(Host).all()
            for host in hosts:
                host.context.append(HostContext())
            db_session.commit()
        except:
            pass

