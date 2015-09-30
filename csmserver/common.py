from sqlalchemy import or_, and_

from constants import ServerType
from constants import UserPrivilege
from constants import InstallAction
from constants import PackageState

from models import Server
from models import Host
from models import JumpHost
from models import Region
from models import User
from models import SMTPServer
from models import logger
from models import Package

from database import DBSession

from filters import get_datetime_string
from filters import time_difference_UTC 

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
    
def get_last_successful_inventory_elapsed_time(host):
    if host is not None:
        # Last inventory successful time
        inventory_job = host.inventory_job[0]
        if inventory_job.pending_submit:
            return 'Pending Retrieval'
        else:
            return  time_difference_UTC(inventory_job.last_successful_time)
        
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
    
