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
from utils import create_directory
from utils import is_ldap_supported

from constants import get_csm_data_directory
from constants import get_log_directory
from constants import get_repository_directory
from constants import get_temp_directory
from constants import get_migration_directory
from constants import get_doc_central_directory

import os
import shutil

# Handle legacy: Rename directory autlogs to log
if os.path.isdir(os.path.join(get_csm_data_directory(), 'autlogs')):
    shutil.move(os.path.join(get_csm_data_directory(), 'autlogs'), get_log_directory())


def relocate_database_ini():
    csm_data_database_ini = os.path.join(get_csm_data_directory(), 'database.ini')
    if not os.path.isfile(csm_data_database_ini):
        shutil.move(os.path.join(os.getcwd(), 'database.ini'), csm_data_database_ini)


def init():
    # Create the necessary supporting directories
    create_directory(get_log_directory())
    create_directory(get_repository_directory())
    create_directory(get_temp_directory())
    create_directory(get_migration_directory())
    create_directory(get_doc_central_directory())

    if not is_ldap_supported():
        print('LDAP authentication is not supported because it has not been installed.')

    # For refresh installation, move database.ini to csm_data
    # relocate_database_ini()


if __name__ == '__main__':
    init()
