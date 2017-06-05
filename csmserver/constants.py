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

NAME_CSM_DATA = 'csm_data'
NAME_REPOSITORY = 'repository'
NAME_LOGS = 'logs'
NAME_TEMP = 'temp'
NAME_MIGRATION = 'migration'

DIRECTORY_CSM_DATA = '../../' + NAME_CSM_DATA + '/'
DIRECTORY_LOG = DIRECTORY_CSM_DATA + NAME_LOGS + '/'
DIRECTORY_REPOSITORY = DIRECTORY_CSM_DATA + NAME_REPOSITORY + '/'
DIRECTORY_TEMP = DIRECTORY_CSM_DATA + NAME_TEMP + '/'
DIRECTORY_MIGRATION = DIRECTORY_CSM_DATA + NAME_MIGRATION + '/'
DIRECTORY_DOC_CENTRAL = DIRECTORY_CSM_DATA + 'doc_central/'


def get_csm_data_directory():
    return DIRECTORY_CSM_DATA


def get_log_directory():
    return DIRECTORY_LOG


def get_repository_directory():
    return DIRECTORY_REPOSITORY


def get_temp_directory():
    return DIRECTORY_TEMP


def get_migration_directory():
    return DIRECTORY_MIGRATION


def get_doc_central_directory():
    return DIRECTORY_DOC_CENTRAL


BUG_SEARCH_URL = 'https://tools.cisco.com/bugsearch/bug/'


class ConnectionType:
    TELNET = 'telnet'
    SSH = 'ssh'


class PlatformFamily:
    ASR9K = 'ASR9K'
    ASR9K_X64 = 'ASR9K-X64'
    ASR900 = 'ASR900'
    CRS = 'CRS'
    NCS1K = 'NCS1K'
    NCS4K = 'NCS4K'
    NCS5K = 'NCS5K'
    NCS5500 = 'NCS5500'
    NCS6K = 'NCS6K'
    N9K = 'N9K'
    IOSXRv_9K = 'IOSXRv-9K'
    IOSXRv_X64 = 'IOSXRv-X64'


class PackageState:
    INACTIVE = 'inactive'
    INACTIVE_COMMITTED = 'inactive-committed'
    ACTIVE = 'active'
    ACTIVE_COMMITTED = 'active-committed'


class JobStatus:
    SCHEDULED = 'scheduled'
    IN_PROGRESS = 'in-progress'
    FAILED = 'failed'
    COMPLETED = 'completed'


class ServerType:
    TFTP_SERVER = 'TFTP'
    FTP_SERVER = 'FTP'
    SFTP_SERVER = 'SFTP'
    SCP_SERVER = 'SCP'
    LOCAL_SERVER = 'LOCAL'


class InstallAction:
    UNKNOWN = 'Unknown'
    PRE_UPGRADE = 'Pre-Upgrade'
    INSTALL_ADD = 'Add'
    INSTALL_PREPARE = 'Prepare'
    INSTALL_ACTIVATE = 'Activate'
    POST_UPGRADE = 'Post-Upgrade'
    INSTALL_COMMIT = 'Commit'
    ALL = 'ALL'
    INSTALL_REMOVE = 'Remove'
    INSTALL_REMOVE_ALL_INACTIVE = 'Remove All Inactive'
    INSTALL_DEACTIVATE = 'Deactivate'
    INSTALL_ROLLBACK = 'Rollback'
    MIGRATION_AUDIT = 'Migration-Audit'
    PRE_MIGRATE = 'Pre-Migrate'
    MIGRATE_SYSTEM = 'Migrate'
    POST_MIGRATE = 'Post-Migrate'
    ALL_FOR_MIGRATE = 'ALL (for Migration)'
    FPD_UPGRADE = 'FPD-Upgrade'


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


class HostConformanceStatus:
    CONFORM = 'Yes'
    NON_CONFORM = 'No'


def get_user_privilege_list():
    return [UserPrivilege.ADMIN, UserPrivilege.NETWORK_ADMIN, UserPrivilege.OPERATOR, UserPrivilege.VIEWER]

class SMTPSecureConnection:
    SSL = 'SSL'
    TLS = 'TLS'


class ProxyAgent:
    CSM_SERVER = 'CSM Server'
    HOST_AGENT = 'Host Agent'


class DefaultHostAuthenticationChoice:
    ALL_HOSTS = "1"
    HOSTS_WITH_NO_SPECIFIED_USERNAME_AND_PASSWORD = "2"


class ExportInformationFormat:
    HTML = 'HTML'
    MICROSOFT_EXCEL = 'Microsoft Excel'
    CSV = 'CSV'


class ExportSoftwareInformationLayout:
    CONCISE = 'Concise'
    DEFAULT = 'Default'
