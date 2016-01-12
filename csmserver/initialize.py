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
from models import initialize
from models import SystemVersion 
from sqlalchemy import inspect
from database import DBSession, CURRENT_SCHEMA_VERSION, engine

from utils import create_directory, is_ldap_supported
from constants import get_autlogs_directory, get_repository_directory, get_temp_directory
from schema.loader import get_schema_migrate_class

import traceback

# Create the necessary supporting directories
create_directory(get_autlogs_directory())
create_directory(get_repository_directory())
create_directory(get_temp_directory())


def init():
    if not is_ldap_supported():
        print('LDAP authentication is not supported because it has not been installed.')

    db_session = DBSession()
    system_version = SystemVersion.get(db_session)

    # Handles database schema migration starting from the next schema version
    for version in range(system_version.schema_version + 1, CURRENT_SCHEMA_VERSION + 1):
        handler_class = get_schema_migrate_class(version)
        if handler_class is not None:
            try:
                handler_class(version).execute()
            except:
                print(traceback.format_exc())

    # Initialize certain tables 
    initialize()

if __name__ == '__main__':
    init()