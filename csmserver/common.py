from flask.ext.login import current_user
from sqlalchemy import or_, and_
from platform_matcher import get_platform
from platform_matcher import get_release

from constants import ServerType
from constants import UserPrivilege
from constants import InstallAction
from constants import JobStatus
from constants import PackageState
from constants import JobStatus

from models import Server
from models import Host
from models import JumpHost
from models import Region
from models import User
from models import SMTPServer
from models import logger
from models import InstallJob
from models import SMUMeta
from models import DownloadJob
from models import get_download_job_key_dict

from smu_utils import SP_INDICATOR
from utils import is_empty, get_datetime
from models import Package
from models import InstallJob
from models import SMUMeta
from models import DownloadJob
from models import get_download_job_key_dict

from database import DBSession

from filters import get_datetime_string
from filters import time_difference_UTC

from smu_utils import SP_INDICATOR, TAR_INDICATOR
from utils import is_empty, get_datetime

def fill_servers(choices, servers, include_local=True):
    # Remove all the existing entries
    del choices[:]
    choices.append((-1, ''))
    
    if len(servers) > 0:
        for server in servers:
            if include_local or server.server_type != ServerType.LOCAL_SERVER:
                choices.append((server.id, server.hostname))
             
                    
def fill_dependencies(choices):
    # Remove all the existing entries
    del choices[:] 
    choices.append((-1, 'None'))  
     
    # The install action is listed in implicit ordering.  This ordering
    # is used to formulate the dependency.
    choices.append((InstallAction.PRE_UPGRADE, InstallAction.PRE_UPGRADE))
    choices.append((InstallAction.INSTALL_ADD, InstallAction.INSTALL_ADD))
    choices.append((InstallAction.INSTALL_ACTIVATE, InstallAction.INSTALL_ACTIVATE)) 
    choices.append((InstallAction.POST_UPGRADE, InstallAction.POST_UPGRADE))
    choices.append((InstallAction.INSTALL_COMMIT, InstallAction.INSTALL_COMMIT)) 

def fill_dependency_from_host_install_jobs(choices, install_jobs, current_install_job_id):
    # Remove all the existing entries
    del choices[:]
    choices.append((-1, 'None'))
    
    for install_job in install_jobs:
        if install_job.id != current_install_job_id:
            choices.append((install_job.id, '%s - %s' % (install_job.install_action, 
                get_datetime_string(install_job.scheduled_time)) ))

def fill_jump_hosts(choices):
    # Remove all the existing entries
    del choices[:]
    choices.append((-1, 'None'))
    
    # do not close session as the caller will do it
    db_session = DBSession()
    try:
        hosts = get_jump_host_list(db_session)
        if hosts is not None:
            for host in hosts:
                choices.append((host.id, host.hostname))
    except:
        logger.exception('fill_jump_hosts() hits exception')

def fill_regions(choices):
    # Remove all the existing entries
    del choices[:]
    choices.append((-1, ''))
    
    # do not close session as the caller will do it
    db_session = DBSession()
    try:
        regions = get_region_list(db_session)
        if regions is not None:
            for region in regions:
                choices.append((region.id, region.name))
    except:
        logger.exception('fill_regions() hits exception')

def fill_default_region(choices, region):
    # Remove all the existing entries
    del choices[:]

    # do not close session as the caller will do it
    db_session = DBSession()
    try:
        if region is not None:
            choices.append((region.id, region.name))
    except:
        logger.exception('fill_default_region() hits exception')

    
def get_last_successful_inventory_elapsed_time(host):
    if host is not None:
        # Last inventory successful time
        inventory_job = host.inventory_job[0]
        if inventory_job.pending_submit:
            return 'Pending Retrieval'
        else:
            return time_difference_UTC(inventory_job.last_successful_time)
        
    return ''

"""
Returns a list of active/active-committed packages.  The list includes SMU/SP/Packages.
"""
def get_host_active_packages(hostname):
    db_session = DBSession()
    host = get_host(db_session, hostname)
    
    result_list = []       
    if host is not None:
        packages = db_session.query(Package).filter(
            and_(Package.host_id == host.id, or_(Package.state == PackageState.ACTIVE, Package.state == PackageState.ACTIVE_COMMITTED) )).all()      
        for package in packages:
            result_list.append(package.name)
    
    return result_list

"""
Returns a list of inactive packages.  The list includes SMU/SP/Packages.
"""
def get_host_inactive_packages(hostname):
    db_session = DBSession()
    host = get_host(db_session, hostname)
    
    result_list = []       
    if host is not None:
        packages = db_session.query(Package).filter(
            and_(Package.host_id == host.id, Package.state == PackageState.INACTIVE) ).all()      
        for package in packages:
            result_list.append(package.name)
    
    return result_list

def get_server_list(db_session):
    return db_session.query(Server).order_by(Server.hostname.asc()).all()

def get_host(db_session, hostname):
    return db_session.query(Host).filter(Host.hostname == hostname).first()

def get_host_list(db_session):
    return db_session.query(Host).order_by(Host.hostname.asc()).all()

def get_jump_host_by_id(db_session, id):
    return db_session.query(JumpHost).filter(JumpHost.id == id).first()

def get_jump_host(db_session, hostname):
    return db_session.query(JumpHost).filter(JumpHost.hostname == hostname).first()

def get_jump_host_list(db_session):
    return db_session.query(JumpHost).order_by(JumpHost.hostname.asc()).all()

def get_server(db_session, hostname):
    return db_session.query(Server).filter(Server.hostname == hostname).first()

def get_server_by_id(db_session, id):
    return db_session.query(Server).filter(Server.id == id).first()

def get_region(db_session, region_name):
    return db_session.query(Region).filter(Region.name == region_name).first()

def get_region_by_id(db_session, region_id):
    return db_session.query(Region).filter(Region.id == region_id).first()

def get_region_list(db_session):
    return db_session.query(Region).order_by(Region.name.asc()).all()

def get_user(db_session, username):
    return db_session.query(User).filter(User.username == username).first()

def get_user_by_id(db_session, user_id):
    return db_session.query(User).filter(User.id == user_id).first()

def get_user_list(db_session):
    return db_session.query(User).order_by(User.fullname.asc()).all()

def get_smtp_server(db_session):
    return db_session.query(SMTPServer).first()

def can_check_reachability(current_user):
    return current_user.privilege == UserPrivilege.ADMIN or \
        current_user.privilege == UserPrivilege.NETWORK_ADMIN or \
        current_user.privilege == UserPrivilege.OPERATOR

def can_retrieve_software(current_user):
    return current_user.privilege == UserPrivilege.ADMIN or \
        current_user.privilege == UserPrivilege.NETWORK_ADMIN or \
        current_user.privilege == UserPrivilege.OPERATOR

def can_install(current_user):
    return current_user.privilege == UserPrivilege.ADMIN or \
        current_user.privilege == UserPrivilege.NETWORK_ADMIN or \
        current_user.privilege == UserPrivilege.OPERATOR

def can_delete_install(current_user):
    return current_user.privilege == UserPrivilege.ADMIN or \
        current_user.privilege == UserPrivilege.NETWORK_ADMIN or \
        current_user.privilege == UserPrivilege.OPERATOR

def can_edit_install(current_user):
    return current_user.privilege == UserPrivilege.ADMIN or \
        current_user.privilege == UserPrivilege.NETWORK_ADMIN or \
        current_user.privilege == UserPrivilege.OPERATOR

def can_create_user(current_user):
    return current_user.privilege == UserPrivilege.ADMIN

def can_edit(current_user):
    return can_create(current_user)

def can_delete(current_user):
    return can_create(current_user)

def can_create(current_user):
    return current_user.privilege == UserPrivilege.ADMIN or \
        current_user.privilege == UserPrivilege.NETWORK_ADMIN 

"""
Returns the return_url encoded in the parameters
"""
def get_return_url(request, default_url=None):
    url = request.args.get('return_url')
    if url is None:
        url = default_url
    return url



def get_first_install_action(db_session, install_action):
    return db_session.query(InstallJob).filter(InstallJob.install_action == install_action). \
        order_by(InstallJob.scheduled_time.asc()).first()


def create_or_update_install_job(
    db_session, host_id, install_action, scheduled_time, software_packages=None,
    server=-1, server_directory='', dependency=0, pending_downloads=None, install_job=None, best_effort_config=0, config_filename=''):

    # This is a new install_job
    if install_job is None:
        install_job = InstallJob()
        install_job.host_id = host_id
        db_session.add(install_job)

    install_job.install_action = install_action

    if install_job.install_action == InstallAction.INSTALL_ADD and \
        not is_empty(pending_downloads):
        install_job.pending_downloads = ','.join(pending_downloads.split())
    else:
        install_job.pending_downloads = ''

    install_job.scheduled_time = get_datetime(scheduled_time, "%m/%d/%Y %I:%M %p")

    # Only Install Add and Pre-Migrate should have server_id and server_directory
    if install_action == InstallAction.INSTALL_ADD or install_action == InstallAction.PRE_MIGRATE:
        install_job.server_id = int(server) if int(server) > 0 else None
        install_job.server_directory = server_directory
    else:
        install_job.server_id = None
        install_job.server_directory = ''

    install_job_packages = []

    # Only the following install actions should have software packages
    if install_action == InstallAction.INSTALL_ADD or \
        install_action == InstallAction.INSTALL_ACTIVATE or \
        install_action == InstallAction.INSTALL_REMOVE or \
        install_action == InstallAction.INSTALL_DEACTIVATE or \
        install_action == InstallAction.PRE_MIGRATE:

        if install_action == InstallAction.PRE_MIGRATE:
            software_packages = software_packages.split(',') if software_packages is not None else []
        else:
            software_packages = software_packages.split() if software_packages is not None else []

        for software_package in software_packages:
            if install_action == InstallAction.INSTALL_ADD:
                # Install Add only accepts external package names with the following suffix
                if '.pie' in software_package or \
                    '.tar' in software_package or \
                    '.rpm' in software_package:

                    install_job_packages.append(software_package)
            else:
                # Install Activate can have external or internal package names
                install_job_packages.append(software_package)

    install_job.packages = ','.join(install_job_packages)
    install_job.dependency = dependency if dependency > 0 else None
    install_job.created_by = current_user.username
    install_job.user_id = current_user.id

    #Resets the following fields
    install_job.status = None
    install_job.status_time = None
    install_job.session_log = None
    install_job.trace = None

    # for post-migrate
    install_job.best_effort_config_applying = best_effort_config

    # for pre-migrate
    install_job.config_filename = config_filename
    print "in create_and_update, install_job.config_filename = " + install_job.config_filename

    if install_job.install_action != InstallAction.UNKNOWN:
        db_session.commit()

    # Creates download jobs if needed
    if install_job.install_action == InstallAction.INSTALL_ADD and \
        len(install_job.packages) > 0 and \
        len(install_job.pending_downloads) > 0:

        # Use the SMU name to derive the platform and release strings
        smu_list = install_job.packages.split(',')
        pending_downloads = install_job.pending_downloads.split(',')

        # Derives the platform and release using the first SMU name.
        platform = get_platform(smu_list[0])
        release = get_release(smu_list[0])

        create_download_jobs(db_session, platform, release, pending_downloads,
            install_job.server_id, install_job.server_directory)

    return install_job

"""
Pending downloads is an array of TAR files.
"""
def create_download_jobs(db_session, platform, release, pending_downloads, server_id, server_directory):
    smu_meta = db_session.query(SMUMeta).filter(SMUMeta.platform_release == platform + '_' + release).first()
    if smu_meta is not None:
        for cco_filename in pending_downloads:
            # If the requested download_file is not in the download table, include it
            if not is_pending_on_download(db_session, cco_filename, server_id, server_directory):
                # Unfortunately, the cco_filename may not conform to the SMU format (i.e. CSC).
                # For example, for CRS, it is possible to have hfr-px-5.1.2.CRS-X-2.tar which contains
                # multiple pie file. Thus, we check if it has a "sp" substring.
                if SP_INDICATOR in cco_filename:
                    software_type_id = smu_meta.sp_software_type_id
                elif TAR_INDICATOR in cco_filename:
                    software_type_id = smu_meta.tar_software_type_id
                else:
                    software_type_id = smu_meta.smu_software_type_id

                download_job = DownloadJob(
                    cco_filename = cco_filename,
                    pid = smu_meta.pid,
                    mdf_id = smu_meta.mdf_id,
                    software_type_id = software_type_id,
                    server_id = server_id,
                    server_directory = server_directory,
                    user_id = current_user.id,
                    created_by = current_user.username)

                db_session.add(download_job)

            db_session.commit()

def is_pending_on_download(db_session, filename, server_id, server_directory):
    download_job_key_dict = get_download_job_key_dict()
    download_job_key = get_download_job_key(current_user.id, filename, server_id, server_directory)

    if download_job_key in download_job_key_dict:
        download_job = download_job_key_dict[download_job_key]
        # Resurrect the download job
        if download_job is not None and download_job.status == JobStatus.FAILED:
            download_job.status = None
            download_job.status_time = None
            db_session.commit()
        return True

    return False


def get_download_job_key(user_id, filename, server_id, server_directory):
    return "{}{}{}{}".format(user_id, filename, server_id, server_directory)
