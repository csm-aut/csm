DIRECTORY_AUT_LOGS = '../autlogs'
DIRECTORY_REPOSITORY = '../repository'
DIRECTORY_TEMP = '../temp'

class ConnectionType:
    TELNET = 'telnet'
    SSH = 'ssh'
    
class Platform:
    ASR9K = 'ASR9K'
    CRS = 'CRS'
    NCS6K = 'NCS6K'
    
class PackageState:
    INACTIVE = 'inactive'
    INACTIVE_COMMITTED = 'inactive-committed'
    ACTIVE = 'active'
    ACTIVE_COMMITTED = 'active-committed'
    
class PackageStateForTab:
    INACTIVE = 'Inactive'
    INACTIVE_COMMITTED = 'Inactive Committed'
    ACTIVE = 'Active'
    ACTIVE_COMMITTED = 'Active Committed'
 
class JobStatus:
    SUBMITTED = 'submitted'
    PROCESSING = 'processing'
    FAILED = 'failed'
    COMPLETED = 'completed'

class ServerType:
    TFTP_SERVER = 'TFTP'
    FTP_SERVER = 'FTP'
    SFTP_SERVER = 'SFTP'
     
class InstallAction:
    UNKNOWN = 'Unknown'
    PRE_UPGRADE = 'Pre-Upgrade'
    INSTALL_ADD = 'Install Add'
    ACTIVATE = 'Activate'
    POST_UPGRADE = 'Post-Upgrade'
    ALL = 'ALL'

class PackageType:
    SMU = 'SMU'
    SMU_IN_TRANSIT = 'SMU In-transit'
    SERVICE_PACK = 'Service Pack'
    PACKAGE = 'Package'
        
class UserPrivilege:
    ADMIN = 'Admin'
    OPERATOR = 'Operator'
    VIEWER = 'Viewer'
    
class SMTPSecureConnection:
    SSL = 'SSL'
    TLS = 'TLS'
    
class ProxyAgent:
    CSM_SERVER = 'CSM Server'
    HOST_AGENT = 'Host Agent'
  