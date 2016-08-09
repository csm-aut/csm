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
from flask.ext.login import current_user
from flask import g, send_file
from sqlalchemy import or_, and_

from csm_exceptions.exceptions import HostNotFound

from constants import ServerType
from constants import UserPrivilege
from constants import InstallAction
from constants import PackageState
from constants import JobStatus

from models import Server
from models import Host
from models import JumpHost
from models import Region
from models import User
from models import SMTPServer
from models import logger

from models import Package
from models import InstallJob
from models import SMUMeta
from models import DownloadJob
from models import InventoryJobHistory
from models import InstallJobHistory
from models import CustomCommandProfile
from models import get_download_job_key_dict
from models import InventoryJob
from models import HostContext
from models import ConnectionParam

from database import DBSession

from filters import get_datetime_string
from filters import time_difference_UTC

from smu_utils import SP_INDICATOR
from smu_utils import TAR_INDICATOR

from utils import get_log_directory
from utils import is_empty
from utils import get_datetime
from utils import remove_extra_spaces
from utils import create_directory
from utils import create_temp_user_directory
from utils import make_file_writable

from smu_info_loader import SMUInfoLoader

import os
import shutil
import zipfile


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
                            get_datetime_string(install_job.scheduled_time))))


def delete_install_job_dependencies(db_session, id):
    deleted = []
    dependencies = db_session.query(InstallJob).filter(InstallJob.dependency == id).all()
    for dependency in dependencies:
        if dependency.status is None:
            db_session.delete(dependency)
            deleted.append(dependency.id)
        deleted = list(set((delete_install_job_dependencies(db_session, dependency.id)) + deleted))
    return deleted


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
        logger.exception('fill_jump_hosts() hit exception')


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
        logger.exception('fill_regions() hit exception')


def fill_default_region(choices, region):
    # Remove all the existing entries
    del choices[:]

    try:
        if region is not None:
            choices.append((region.id, region.name))
    except:
        logger.exception('fill_default_region() hits exception')


def fill_custom_command_profiles(choices):
    del choices[:]

    db_session = DBSession()
    try:
        profiles = get_custom_command_profiles_list(db_session)

        for profile in profiles:
            choices.append((profile.id, profile.profile_name))

    except:
        logger.exception('fill_custom_command_profiles() hit exception')


def get_last_successful_inventory_elapsed_time(host):
    if host is not None:
        # Last inventory successful time
        inventory_job = host.inventory_job[0]
        if inventory_job.request_update:
            return 'Pending Retrieval'
        else:
            if inventory_job.last_successful_time is None:
                return 'None'
            else:
                return time_difference_UTC(inventory_job.last_successful_time)

    return ''


def get_host_active_packages(hostname):
    """
    Returns a list of active/active-committed packages.  The list includes SMU/SP/Packages.
    """
    db_session = DBSession()
    host = get_host(db_session, hostname)

    result_list = []
    if host is not None:
        packages = db_session.query(Package).filter(
            and_(Package.host_id == host.id, or_(Package.state == PackageState.ACTIVE,
                                                 Package.state == PackageState.ACTIVE_COMMITTED))).all()
        for package in packages:
            result_list.append(package.name)

    return result_list


def get_host_inactive_packages(hostname):
    """
    Returns a list of inactive packages.  The list includes SMU/SP/Packages.
    """
    db_session = DBSession()
    host = get_host(db_session, hostname)

    result_list = []
    if host is not None:
        packages = db_session.query(Package).filter(
            and_(Package.host_id == host.id, Package.state == PackageState.INACTIVE)).all()
        for package in packages:
            result_list.append(package.name)

    return result_list


def get_server_list(db_session):
    return db_session.query(Server).order_by(Server.hostname.asc()).all()


def get_host(db_session, hostname):
    return db_session.query(Host).filter(Host.hostname == hostname).first()


def get_host_by_id(db_session, id):
    return db_session.query(Host).filter(Host.id == id).first()


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


def get_custom_command_profile_by_id(db_session, id):
    return db_session.query(CustomCommandProfile).filter(CustomCommandProfile.id == id).first()


def get_region(db_session, region_name):
    return db_session.query(Region).filter(Region.name == region_name).first()


def get_region_by_id(db_session, region_id):
    return db_session.query(Region).filter(Region.id == region_id).first()


def get_region_list(db_session):
    return db_session.query(Region).order_by(Region.name.asc()).all()


def get_custom_command_profiles_list(db_session):
    return db_session.query(CustomCommandProfile).order_by(CustomCommandProfile.profile_name.asc()).all()


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


def get_return_url(request, default_url=None):
    """
    Returns the return_url encoded in the parameters
    """
    url = request.args.get('return_url')
    if url is None:
        url = default_url
    return url


def get_last_install_action(db_session, install_action, host_id):
    return db_session.query(InstallJob).filter(and_(InstallJob.install_action == install_action,
                                               InstallJob.host_id == host_id)). \
        order_by(InstallJob.scheduled_time.desc()).first()


def get_install_job_dependency_completed(db_session, install_action, host_id):
    return db_session.query(InstallJobHistory).filter(and_(InstallJobHistory.install_action == install_action,
                                                           InstallJobHistory.host_id == host_id,
                                                           InstallJobHistory.status == JobStatus.COMPLETED)).all()


def create_or_update_host(db_session, hostname, region_id, roles, connection_type, host_or_ip,
                username, password, enable_password, port_number, jump_host_id, created_by, host=None):
    """ Create a new host in the Database """
    if host is None:
        host = Host(hostname=hostname, created_by=created_by)
        host.inventory_job.append(InventoryJob())
        host.context.append(HostContext())
        db_session.add(host)

    host.region_id = region_id if region_id > 0 else None
    host.roles = '' if roles is None else remove_extra_spaces(roles)
    host.connection_param = [ConnectionParam(
        # could have multiple IPs, separated by comma
        host_or_ip='' if host_or_ip is None else remove_extra_spaces(host_or_ip),
        username='' if username is None else username,
        password='' if password is None else password,
        enable_password='' if enable_password is None else enable_password,
        jump_host_id=jump_host_id if jump_host_id > 0 else None,
        connection_type=connection_type,
        # could have multiple ports, separated by comma
        port_number='' if port_number is None else remove_extra_spaces(port_number))]

    db_session.commit()

    return host


def delete_host(db_session, hostname):
    host = get_host(db_session, hostname)
    if host is None:
        raise HostNotFound('Unable to locate host %s' % hostname)

    delete_host_inventory_job_session_logs(db_session, host)
    delete_host_install_job_session_logs(db_session, host)
    db_session.delete(host)
    db_session.commit()


def delete_host_inventory_job_session_logs(db_session, host):
    inventory_jobs = db_session.query(InventoryJobHistory).filter(InventoryJobHistory.host_id == host.id)
    for inventory_job in inventory_jobs:
        try:
            shutil.rmtree(os.path.join(get_log_directory(), inventory_job.session_log))
        except:
            logger.exception('delete_host_inventory_job_session_logs() hit exception')


def delete_host_install_job_session_logs(db_session, host):
    install_jobs = db_session.query(InstallJobHistory).filter(InstallJobHistory.host_id == host.id)
    for install_job in install_jobs:
        try:
            shutil.rmtree(os.path.join(get_log_directory(), install_job.session_log))
        except:
            logger.exception('delete_host_install_job_session_logs() hit exception')


def create_or_update_install_job(db_session, host_id, install_action, scheduled_time, software_packages=None,
                                 server=-1, server_directory='', custom_command_profile=-1, dependency=0,
                                 pending_downloads=None, install_job=None):

    # ASR9K, CRS: .pie, .tar
    # NCS6K: .smu, .iso, .pkg, .tar
    # ASR9K-64: .iso, .rpm, .tar
    acceptable_package_types_for_add = ['.pie', '.rpm', '.tar', '.smu', '.iso', '.pkg']

    # This is a new install_job
    if install_job is None:
        install_job = InstallJob()
        install_job.host_id = host_id
        db_session.add(install_job)

    install_job.install_action = install_action

    if install_job.install_action == InstallAction.INSTALL_ADD and not is_empty(pending_downloads):
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
                if any(ext in software_package for ext in acceptable_package_types_for_add):
                    install_job_packages.append(software_package)
            else:
                # Install Activate can have external or internal package names
                install_job_packages.append(software_package)

    install_job.packages = ','.join(install_job_packages)
    install_job.dependency = dependency if dependency > 0 else None

    if hasattr(current_user, 'username'):
        install_job.created_by = current_user.username
        install_job.user_id = current_user.id
    else:
        install_job.created_by = g.api_user.username
        install_job.user_id = g.api_user.id

    if install_action == InstallAction.PRE_UPGRADE or install_action == InstallAction.POST_UPGRADE or \
       install_action == InstallAction.PRE_MIGRATE or install_action == InstallAction.MIGRATE_SYSTEM or \
       install_action == InstallAction.POST_MIGRATE:
        install_job.custom_command_profile_id = custom_command_profile if custom_command_profile else None

    # Resets the following fields
    install_job.status = None
    install_job.status_time = None
    install_job.session_log = None
    install_job.trace = None

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
        platform, release = SMUInfoLoader.get_platform_and_release(smu_list)

        create_download_jobs(db_session, platform, release, pending_downloads,
                             install_job.server_id, install_job.server_directory)

    return install_job


def create_download_jobs(db_session, platform, release, pending_downloads, server_id, server_directory):
    """
    Pending downloads is an array of TAR files.
    """
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
                    cco_filename=cco_filename,
                    pid=smu_meta.pid,
                    mdf_id=smu_meta.mdf_id,
                    software_type_id=software_type_id,
                    server_id=server_id,
                    server_directory=server_directory,
                    user_id=current_user.id,
                    created_by=current_user.username)

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


# Accepts an array containing paths to specific files
def download_session_logs(file_list):
    if hasattr(current_user, 'username'):
        username = current_user.username
    else:
        username = g.api_user.username

    temp_user_dir = create_temp_user_directory(username)
    session_zip_path = os.path.normpath(os.path.join(temp_user_dir, "session_logs"))
    zip_file = os.path.join(session_zip_path, "session_logs.zip")
    create_directory(session_zip_path)
    make_file_writable(session_zip_path)

    zout = zipfile.ZipFile(zip_file, mode='w')
    for f in file_list:
        zout.write(os.path.normpath(f), os.path.basename(f))

    zout.close()

    return send_file(zip_file, as_attachment=True)


def get_last_completed_install_job_for_install_action(db_session, host_id, install_action):
    return db_session.query(InstallJobHistory). \
        filter(and_(InstallJobHistory.host_id == host_id,
                    InstallJobHistory.install_action == install_action,
                    InstallJobHistory.status == JobStatus.COMPLETED)). \
        order_by(InstallJobHistory.status_time.desc()).first()


def get_download_job_key(user_id, filename, server_id, server_directory):
    return "{}{}{}{}".format(user_id, filename, server_id, server_directory)
