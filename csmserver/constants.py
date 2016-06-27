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
CSM Server Directory Structure
csm
  aut
    au
  csmserver
csm_data
  autlogs
  repository
  temp
"""
UNKNOWN = 'Unknown'
DIRECTORY_BASE = '../../csm_data/'
DIRECTORY_LOG = DIRECTORY_BASE + 'autlogs/'
DIRECTORY_REPOSITORY = DIRECTORY_BASE + 'repository/'
DIRECTORY_TEMP = DIRECTORY_BASE + 'temp/'
DIRECTORY_MIGRATION = DIRECTORY_BASE + 'migration/'


def get_csm_data_directory():
    return DIRECTORY_BASE


def get_log_directory():
    return DIRECTORY_LOG


def get_repository_directory():
    return DIRECTORY_REPOSITORY


def get_temp_directory():
    return DIRECTORY_TEMP


def get_migration_directory():
    return DIRECTORY_MIGRATION

BUG_SEARCH_URL = 'https://tools.cisco.com/bugsearch/bug/'


class ConnectionType:
    TELNET = 'telnet'
    SSH = 'ssh'


class PlatformFamily:
    ASR9K = 'ASR9K'
    CRS = 'CRS'
    NCS6K = 'NCS6K'
    NCS5K = 'NCS5K'
    NCS5500 = 'NCS5500'
    ASR9K_64 = 'ASR9K-64'
    ASR900 = 'ASR900'
    N9K = 'N9K'


class PackageState:
    INACTIVE = 'inactive'
    INACTIVE_COMMITTED = 'inactive-committed'
    ACTIVE = 'active'
    ACTIVE_COMMITTED = 'active-committed'


class JobStatus:
    SUBMITTED = 'submitted'
    PROCESSING = 'processing'
    FAILED = 'failed'
    COMPLETED = 'completed'


class ServerType:
    TFTP_SERVER = 'TFTP'
    FTP_SERVER = 'FTP'
    SFTP_SERVER = 'SFTP'
    LOCAL_SERVER = 'LOCAL'


class InstallAction:
    UNKNOWN = 'Unknown'
    PRE_UPGRADE = 'Pre-Upgrade'
    INSTALL_ADD = 'Add'
    INSTALL_ACTIVATE = 'Activate'
    POST_UPGRADE = 'Post-Upgrade'
    INSTALL_COMMIT = 'Commit'
    ALL = 'ALL'
    INSTALL_REMOVE = 'Remove'
    INSTALL_DEACTIVATE = 'Deactivate'
    INSTALL_ROLLBACK = 'Rollback'
    MIGRATION_AUDIT = 'Migration-Audit'
    PRE_MIGRATE = 'Pre-Migrate'
    MIGRATE_SYSTEM = 'Migrate'
    POST_MIGRATE = 'Post-Migrate'
    ALL_FOR_MIGRATE = 'ALL (for Migration)'


class PackageType:
    SMU = 'SMU'
    SMU_IN_TRANSIT = 'SMU In-transit'
    SERVICE_PACK = 'Service Pack'
    PACKAGE = 'Package'
    SOFTWARE = 'Software'


class UserPrivilege:
    ADMIN = 'Admin'
    NETWORK_ADMIN = 'Network Admin'
    OPERATOR = 'Operator'
    VIEWER = 'Viewer'


class SMTPSecureConnection:
    SSL = 'SSL'
    TLS = 'TLS'


class ProxyAgent:
    CSM_SERVER = 'CSM Server'
    HOST_AGENT = 'Host Agent'


class DefaultHostAuthenticationChoice:
    ALL_HOSTS = "1"
    HOSTS_WITH_NO_SPECIFIED_USERNAME_AND_PASSWORD = "2"


class ExportSoftwareInformationFormat:
    HTML = 'HTML'
    MICROSOFT_EXCEL = 'Microsoft Excel'


class ExportSoftwareInformationLayout:
    CONCISE = 'Concise'
    DEFAULT = 'Default'
