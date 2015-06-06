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
from sqlalchemy import Column, Table, Boolean
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, synonym

from utils import make_url
from utils import is_empty
from salts import encode, decode

from database import engine
from database import DBSession 
from database import STRING1, STRING2

from constants import JobStatus
from constants import UserPrivilege
from constants import ProxyAgent

import datetime
import logging
import traceback

from werkzeug import check_password_hash
from werkzeug import generate_password_hash 

# Contains information for password encryption
encrypt_dict = None

Base = declarative_base()

class User(Base):
    """A user login, with credentials and authentication."""
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, index=True)
    # encrypted password is much longer in length
    _password = Column('password', String(100), nullable=False)
    privilege = Column(String(20), nullable=False)   
    fullname = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False)
    active = Column(Boolean, default=True)
    
    # Note the lack of parenthesis after datetime.utcnow.  This is the correct way
    # so SQLAlchemhy can make a run time call during row insertion.
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    modified_time = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    preferences = relationship("Preferences",
        order_by="Preferences.id",
        backref="user",
        cascade="all, delete, delete-orphan")
    
    install_job = relationship("InstallJob",
        order_by="InstallJob.id",
        backref="user",
        cascade="all, delete, delete-orphan")
    
    download_job = relationship("DownloadJob",
        order_by="DownloadJob.id",
        backref="user",
        cascade="all, delete, delete-orphan")
    
    download_job_history = relationship("DownloadJobHistory",
        order_by="desc(DownloadJobHistory.created_time)",
        backref="host",
        cascade="all, delete, delete-orphan")
    
    csm_message = relationship("CSMMessage",
        cascade="all, delete, delete-orphan")

    def _get_password(self):
        return self._password

    def _set_password(self, password):
        if password:
            password = password.strip()
        self._password = generate_password_hash(password)

    password_descriptor = property(_get_password, _set_password)
    password = synonym('_password', descriptor=password_descriptor)

    def check_password(self, password):
        if self.password is None:
            return False
        
        password = password.strip()
        if not password:
            return False
        
        return check_password_hash(self.password, password)

    @classmethod
    def authenticate(cls, query, username, password):
        username = username.strip().lower()
        user = query(cls).filter(cls.username==username).first()
        if user is None:
            return None, False
        
        if not user.active:
            return user, False
        
        return user, user.check_password(password)

    # Hooks for Flask-Login.
    #
    # As methods, these are only valid for User instances, so the
    # authentication will have already happened in the view functions.
    #
    # If you prefer, you can use Flask-Login's UserMixin to get these methods.

    def get_id(self):
        return str(self.id)

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

    def __repr__(self):
        return u'<{self.__class__.__name__}: {self.id}>'.format(self=self)

class Host(Base):
    __tablename__ = 'host'
    
    id = Column(Integer, primary_key=True)
    hostname = Column(String(50), nullable=False, index=True)
    platform = Column(String(20), nullable=False)
    software_platform = Column(String(20))
    software_version = Column(String(20))   
    roles = Column(String(100))
    region_id = Column(Integer, ForeignKey('region.id'))
    proxy_agent = Column(String(30), default=ProxyAgent.CSM_SERVER)
    can_schedule = Column(Boolean, default=True)
    can_install = Column(Boolean, default=True)
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
    region = relationship('Region', foreign_keys='Host.region_id') 
    
    connection_param = relationship("ConnectionParam",
        order_by="ConnectionParam.id",
        backref="host",
        cascade="all, delete, delete-orphan")
    
    inventory_job = relationship("InventoryJob",
        cascade="all, delete, delete-orphan")
    
    inventory_job_history = relationship("InventoryJobHistory",
        order_by="desc(InventoryJobHistory.created_time)",
        backref="host",
        cascade="all, delete, delete-orphan")
    
    packages = relationship("Package",
        order_by="Package.id",
        backref="host",
        cascade="all, delete, delete-orphan")
    
    install_job = relationship("InstallJob",
        order_by="asc(InstallJob.scheduled_time)",
        backref="host",
        cascade="all, delete, delete-orphan")
    
    install_job_history = relationship("InstallJobHistory",
        order_by="desc(InstallJobHistory.created_time)",
        backref="host",
        cascade="all, delete, delete-orphan")
        
    @property
    def urls(self):
        _urls = []
        
        if len(self.connection_param) > 0:
            connection = self.connection_param[0]
            db_session = DBSession()
            # Checks if there is a jump server
            if connection.jump_host_id is not None:
                try:
                    jump_host = db_session.query(JumpHost).filter(JumpHost.id == connection.jump_host_id).first()
                    if jump_host is not None:
                        _urls.append(make_url(
                            connection_type=jump_host.connection_type,
                            username=jump_host.username,
                            password=jump_host.password,
                            host_or_ip=jump_host.host_or_ip,
                            port_number=jump_host.port_number))
                except:
                    logger.exception('Host.urls() hits exception')
            
            default_username=None
            default_password=None
            system_option = SystemOption.get(db_session)
            
            if system_option.enable_default_host_authentication:
                default_username=system_option.default_host_username
                default_password=system_option.default_host_password
                
            _urls.append(make_url(
                connection_type=connection.connection_type,
                username=connection.username,
                password=connection.password,
                host_or_ip=connection.host_or_ip,
                port_number=connection.port_number,
                default_username=default_username,
                default_password=default_password))
        
        return _urls
    
    def get_json(self):
        result = {}
        result['hostname'] = self.hostname
        try:
        
            if len(self.packages) > 0:
                package_list_dict = {}            
            
                # loop through individual package
                for index, package in enumerate(self.packages):

                    package_dict = {} 
                    modules_package_state = package.modules_package_state
                    modules_package_state_dict = {}

                    if modules_package_state:
                        for module_package_state in modules_package_state:
                            modules_package_state_dict[module_package_state.module_name] = \
                                module_package_state.package_state

                    if len(modules_package_state_dict) > 0:
                        package_dict['modules'] = modules_package_state_dict
                    
                    package_dict['state'] = package.state
                    package_dict['package'] = package.name
                    package_list_dict[index] = package_dict
                
                result['packages'] = package_list_dict         
        except:
            logger.exception('Host.get_json() hits exception')  
              
        return result

class ConnectionParam(Base):
    __tablename__ = 'connection_param'
    
    id = Column(Integer, primary_key=True)
    # Multiple IPs can be specified using comma as the delimiter
    host_or_ip = Column(String(100), nullable=False)
    username = Column(String(50), nullable=False)
    _password = Column('password', String(100), nullable=False)
    connection_type = Column(String(10), nullable=False)
    # Multiple Ports can be specified using comma as the delimiter
    port_number = Column(String(100))
    
    host_id = Column(Integer, ForeignKey('host.id'))
    jump_host_id = Column(Integer, ForeignKey('jump_host.id'))
    # jump_host = relationship("JumpHost", backref='connection_param', order_by=jump_host_id)
    jump_host = relationship("JumpHost", foreign_keys='ConnectionParam.jump_host_id')
    
    @property
    def password(self):
        global encrypt_dict
        return decode(encrypt_dict, self._password)
    
    @password.setter
    def password(self, value):
        global encrypt_dict
        self._password = encode(encrypt_dict, value)
    
class JumpHost(Base):
    __tablename__ = 'jump_host'
    
    id = Column(Integer, primary_key=True)
    hostname = Column(String(100), nullable=False, index=True)
    host_or_ip = Column(String(50), nullable=False)
    username = Column(String(50), nullable=False)
    _password = Column('password', String(100), nullable=False)
    connection_type = Column(String(10), nullable=False)
    port_number = Column(String(10))
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
    
    @property
    def password(self):
        global encrypt_dict 
        return decode(encrypt_dict, self._password)
    
    @password.setter
    def password(self, value):
        global encrypt_dict
        self._password = encode(encrypt_dict, value)

class InventoryJob(Base):
    __tablename__ = 'inventory_job'
    
    id = Column(Integer, primary_key=True)
    pending_submit = Column(Boolean, default=True)
    status = Column(String(200))
    status_time = Column(DateTime) 
    last_successful_time = Column(DateTime)
    session_log = Column(Text)
    
    host_id = Column(Integer, ForeignKey('host.id'), unique=True)
    host = relationship('Host', foreign_keys='InventoryJob.host_id')
    
    def set_status(self, status):
        self.status = status
        self.status_time = datetime.datetime.utcnow()
        if self.status == JobStatus.COMPLETED:
            self.last_successful_time = self.status_time
    
class InventoryJobHistory(Base):
    __tablename__ = 'inventory_job_history'
    
    id = Column(Integer, primary_key=True)
    status = Column(String(200))
    status_time = Column(DateTime) 
    trace = Column(Text)
    session_log = Column(Text)
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
                            
    host_id = Column(Integer, ForeignKey('host.id'))
    
    def set_status(self, status):
        self.status = status
        self.status_time = datetime.datetime.utcnow()
    
class Package(Base):
    __tablename__ = 'package'
    
    id = Column(Integer, primary_key=True)
    location = Column(String(20))
    name = Column(String(100), nullable=False)
    state = Column(String(20), nullable=False)  
    
    host_id = Column(Integer, ForeignKey('host.id')) 
    
    modules_package_state = relationship("ModulePackageState",
        order_by="ModulePackageState.module_name",
        backref="package",
        cascade="all, delete, delete-orphan")

class ModulePackageState(Base):
    __tablename__ = 'module_package_state'
    
    id = Column(Integer, primary_key=True)
    module_name = Column(String(20), nullable=False)
    package_state = Column(String(20), nullable=False)
    
    package_id = Column(Integer, ForeignKey('package.id'))


class InstallJob(Base):
    __tablename__ = 'install_job'
    
    id = Column(Integer, primary_key=True)
    install_action = Column(String(50))
    dependency = Column(Integer)
    server_id = Column(Integer, ForeignKey('server.id'))
    server_directory = Column(String(300))
    packages = Column(Text)
    pending_downloads = Column(Text)
    scheduled_time = Column(DateTime)
    start_time = Column(DateTime)
    status = Column(String(200))
    status_time = Column(DateTime) 
    trace = Column(Text)
    session_log = Column(Text)
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    modified_time = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    created_by = Column(String(50))
    
    host_id = Column(Integer, ForeignKey('host.id'))     
    user_id = Column(Integer, ForeignKey('user.id'))
    #host = relationship('Host', foreign_keys='InstallJob.host_id')

    def set_status(self, status):
        self.status = status
        self.status_time = datetime.datetime.utcnow()
    
class InstallJobHistory(Base):
    __tablename__ = 'install_job_history'
    
    id = Column(Integer, primary_key=True)
    install_action = Column(String(50))
    dependency = Column(Integer)
    packages = Column(Text)
    scheduled_time = Column(DateTime)
    start_time = Column(DateTime)
    status = Column(String(200))
    status_time = Column(DateTime) 
    operation_id = Column(Integer, default=-1)
    trace = Column(Text)
    install_job_id = Column(Integer, index=True, unique=False)
    session_log = Column(Text)
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
                            
    host_id = Column(Integer, ForeignKey('host.id'))
    
    def set_status(self, status):
        self.status = status        
        self.status_time = datetime.datetime.utcnow()
 
class Region(Base):
    __tablename__ = 'region'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), index=True)
    
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
    servers = relationship('Server', order_by="Server.hostname", secondary=lambda: RegionServer)
          
class Server(Base):
    __tablename__ = 'server'
    id = Column(Integer, primary_key=True)
    hostname = Column(String(100), index=True)
    server_type = Column(String(20))
    server_url = Column(String(100))
    username = Column(String(100))
    _password = Column('password', String(100))
    server_directory = Column(String(100))
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
    
    @property
    def password(self):
        global encrypt_dict
        return decode(encrypt_dict, self._password)
    
    @password.setter
    def password(self, value):
        global encrypt_dict
        self._password = encode(encrypt_dict, value)
    
class SMTPServer(Base):
    __tablename__ = 'smtp_server'
    id = Column(Integer, primary_key=True)
    server = Column(String(50))
    server_port = Column(String(10))
    sender = Column(String(50))
    use_authentication = Column(Boolean, default=False)
    username = Column(String(50))
    _password = Column('password', String(100))
    secure_connection = Column(String(10))
    
    @property
    def password(self):
        global encrypt_dict
        return decode(encrypt_dict, self._password)
    
    @password.setter
    def password(self, value):
        global encrypt_dict
        self._password = encode(encrypt_dict, value)

RegionServer = Table('region_server', Base.metadata,
    Column('region_id', Integer, ForeignKey("region.id"), primary_key=True),
    Column('server_id', Integer, ForeignKey("server.id"), primary_key=True)
)

class Preferences(Base):
    __tablename__ = 'preferences'
    id = Column(Integer, primary_key=True)
    
    excluded_platforms_and_releases = Column(Text)
    cco_username = Column(String(50))
    _cco_password = Column('cco_password', String(100))
    
    user_id = Column(Integer, ForeignKey('user.id'))
    
    @property
    def cco_password(self):
        global encrypt_dict
        return decode(encrypt_dict, self._cco_password)
    
    @cco_password.setter
    def cco_password(self, value):
        global encrypt_dict
        self._cco_password = encode(encrypt_dict, value)
    
    @classmethod
    def get(cls, db_session, user_id):
        return db_session.query(Preferences).filter(Preferences.user_id == user_id).first()
    
class DownloadJob(Base):
    __tablename__ = 'download_job'  
    id = Column(Integer, primary_key=True)
    cco_filename = Column(String(50))
    scheduled_time = Column(DateTime, default=datetime.datetime.utcnow)
    pid = Column(String(200))
    mdf_id = Column(String(200))
    software_type_id = Column(String(20))
    server_id = Column(Integer)
    server_directory = Column(String(300))
    status = Column(String(200))
    status_time = Column(DateTime) 
    trace = Column(Text)
    session_log = Column(Text)
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
    
    user_id = Column(Integer, ForeignKey('user.id'))
    
    def set_status(self, status):
        self.status = status
        self.status_time = datetime.datetime.utcnow()
        
class DownloadJobHistory(Base):
    __tablename__ = 'download_job_history'   
    id = Column(Integer, primary_key=True)
    cco_filename = Column(String(50))
    scheduled_time = Column(DateTime)
    pid = Column(String(200))
    mdf_id = Column(String(200))
    software_type_id = Column(String(20))
    server_id = Column(Integer)
    server_directory = Column(String(300))
    status = Column(String(200))
    status_time = Column(DateTime) 
    trace = Column(Text)
    session_log = Column(Text)
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
    
    user_id = Column(Integer, ForeignKey('user.id'))
    
    def set_status(self, status):
        self.status = status        
        self.status_time = datetime.datetime.utcnow()

class SMUMeta(Base):
    __tablename__ = 'smu_meta'
    # name is like asr9k_px_4.2.3
    platform_release = Column(String(40), primary_key=True)
    created_time = Column(String(30)) # Use string instead of timestamp
    downloaded_time = Column(String(30))
    smu_software_type_id = Column(String(20))
    sp_software_type_id = Column(String(20))
    file_suffix = Column(String(10))
    pid = Column(String(200))
    mdf_id = Column(String(200))
     
    smu_info = relationship("SMUInfo",
        backref="smu_meta",
        cascade="all, delete, delete-orphan")
    
class SMUInfo(Base):
    __tablename__ = 'smu_info'
    id = Column(String(15), primary_key=True)
    name = Column(String(50))
    status = Column(String(20))
    type = Column(String(20)) # Recommended, Optional, PSIRT
    package_type = Column(String(20)) 
    posted_date = Column(String(30))
    eta_date = Column(String(30))
    ddts = Column(String(20))
    description = Column(Text)
    impact = Column(String(50))
    _cco_filename = Column("cco_filename", String(50))
    functional_areas = Column(Text)              
    package_bundles = Column(Text)
    composite_DDTS = Column(Text)
    compressed_image_size = Column(Integer, default=0)              
    uncompressed_image_size = Column(Integer, default=0)  
    
    supersedes = Column(Text)
    superseded_by = Column(Text)
    prerequisites = Column(Text)
    prerequisite_to = Column(Text)
    platform_release = Column(String(40), ForeignKey('smu_meta.platform_release'))

    @property
    def cco_filename(self):
        # Somehow,PIMS did not fill in the cco_filename
        if is_empty(self._cco_filename):
            return self.name + '.tar'
        return self._cco_filename
    
    @cco_filename.setter
    def cco_filename(self, value):
        self._cco_filename = value
        
class SystemVersion(Base): 
    __tablename__ = 'system_version'
    id = Column(Integer, primary_key=True)
    schema_version = Column(Integer, default=1)
    software_version = Column(String(10), default='1.0')
    
    @classmethod
    def get(cls, db_session):
        return db_session.query(SystemVersion).first()
    
class SystemOption(Base):
    __tablename__ = 'system_option'   
    id = Column(Integer, primary_key=True)
    inventory_threads = Column(Integer, default=5)
    install_threads = Column(Integer, default=10)
    download_threads = Column(Integer, default=5)
    can_schedule = Column(Boolean, default=True)
    can_install = Column(Boolean, default=True)
    enable_email_notify = Column(Boolean, default=False)
    enable_inventory = Column(Boolean, default=True)
    inventory_hour = Column(Integer, default=0)
    inventory_history_per_host = Column(Integer, default=10)
    download_history_per_user = Column(Integer, default=100)
    install_history_per_host = Column(Integer, default=1000)
    total_system_logs = Column(Integer, default=10000)
    enable_default_host_authentication = Column(Boolean, default=False)
    default_host_username = Column(String(50))
    _default_host_password = Column('default_host_password', String(100))
    base_url = Column(String(100))
    
    @property
    def default_host_password(self):
        global encrypt_dict
        return decode(encrypt_dict, self._default_host_password)
    
    @default_host_password.setter
    def default_host_password(self, value):
        global encrypt_dict
        self._default_host_password = encode(encrypt_dict, value)
    
    @classmethod
    def get(cls, db_session):
        return db_session.query(SystemOption).first()
    
class Encrypt(Base):
    __tablename__ = 'encrypt'
    id = Column(Integer, primary_key=True)
    key = Column(String(30), default=datetime.datetime.utcnow().strftime("%m/%d/%Y %I:%M %p"))
    string1 = Column(String(100), 
        default=STRING1)
    string2 = Column(String(100), 
        default=STRING2)
    
    @classmethod
    def get(cls, db_session):
        return db_session.query(Encrypt).first()
    
class Log(Base):
    __tablename__ = 'log'
    
    id = Column(Integer, primary_key=True)
    host_id = Column(Integer)
    level = Column(String(20))
    trace = Column(Text)
    msg = Column(Text)
    log = Column(Text)
    created_time = Column(DateTime)

class CSMMessage(Base):
    __tablename__ = 'csm_message'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    acknowledgment_date = Column(DateTime)
    
Base.metadata.create_all(engine)
        
class LogHandler(logging.Handler):
    def emit(self, record):
    
        trace = traceback.format_exc() if record.__dict__['exc_info'] else None
        
        args = record.__dict__['args']
        msg = record.__dict__['msg']
    
        if len(args) >= 1:
            msg = msg % args
            
        log = Log(
            level=record.__dict__['levelname'],
            trace=trace,
            msg=msg, 
            created_time=datetime.datetime.utcnow())
        
        db_session = DBSession()
        db_session.add(log)
        db_session.commit()
        
logger = logging.getLogger('log')
logger.setLevel(logging.DEBUG)
logger.addHandler(LogHandler())
       
def get_download_job_key_dict():
    result = {}
    db_session = DBSession()
    download_jobs = db_session.query(DownloadJob).all()
    for download_job in download_jobs:
        download_job_key = "{}{}{}{}".format(download_job.user_id,download_job.cco_filename, download_job.server_id, download_job.server_directory)
        result[download_job_key] = download_job
    return result

def init_system_version():
    db_session = DBSession()
    if db_session.query(SystemVersion).count() == 0:
        db_session.add(SystemVersion())
        db_session.commit()
  
def init_user():
    db_session = DBSession()

    # Setup a default cisco user if none exists
    if db_session.query(User).count() == 0:
        user = User(
            username='root',
            password='root',
            privilege=UserPrivilege.ADMIN,
            fullname='admin',
            email='admin')
        user.preferences.append(Preferences())
        db_session.add(user)
        db_session.commit()
        
def init_system_option():
    db_session = DBSession()
    if db_session.query(SystemOption).count() == 0:
        db_session.add(SystemOption())
        db_session.commit()
        
def init_encrypt(): 
    global encrypt_dict

    db_session = DBSession()
    if db_session.query(Encrypt).count() == 0:
        db_session.add(Encrypt())
        db_session.commit()
    encrypt_dict = dict(Encrypt.get(db_session).__dict__)
    
def initialize():
    init_user()
    init_encrypt()       
    init_system_option()

init_system_version()
 
if __name__ == '__main__':
    pass

