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
from sqlalchemy import Column, Table, Boolean
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy import and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext import mutable
from sqlalchemy import ForeignKey
from sqlalchemy.orm import backref, relationship, synonym

from utils import is_empty
from salts import encode, decode

from database import engine
from database import DBSession 
from database import STRING1, STRING2
from database import CURRENT_SCHEMA_VERSION

from constants import UNKNOWN
from constants import JobStatus
from constants import UserPrivilege
from constants import ProxyAgent
from constants import get_log_directory

import datetime
import logging
import traceback
import shutil
import os

from werkzeug import check_password_hash
from werkzeug import generate_password_hash 
from ldap_utils import ldap_auth
from csm_exceptions import CSMLDAPException

from sqlalchemy.types import TypeDecorator, VARCHAR
import json

from itsdangerous import (TimedJSONWebSignatureSerializer
                          as Serializer, BadSignature, SignatureExpired)

from flask.ext.httpauth import HTTPBasicAuth

# Contains information for password encryption
encrypt_dict = None


class JSONEncodedDict(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


mutable.MutableDict.associate_with(JSONEncodedDict)


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

    # host password is used when CSM Server user credential is used for host login.
    _host_password = Column('host_password', String(100))
    
    # Note the lack of parenthesis after datetime.utcnow.  This is the correct way
    # so SQLAlchemhy can make a run time call during row insertion.
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    modified_time = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    preferences = relationship("Preferences",
                               order_by="Preferences.id",
                               backref="user",
                               cascade="all, delete-orphan")
    
    install_job = relationship("InstallJob",
                               order_by="InstallJob.id",
                               backref="user",
                               cascade="all, delete-orphan")
    
    download_job = relationship("DownloadJob",
                                order_by="DownloadJob.id",
                                backref="user",
                                cascade="all, delete-orphan")
    
    download_job_history = relationship("DownloadJobHistory",
                                        order_by="desc(DownloadJobHistory.created_time)",
                                        backref="host",
                                        cascade="all, delete-orphan")
    
    csm_message = relationship("CSMMessage",
                               cascade="all, delete-orphan")

    conformance_report = relationship("ConformanceReport",
                                      cascade="all, delete-orphan")
    
    def _get_password(self):
        return self._password

    def _set_password(self, password):
        if password:
            password = password.strip()

        self.host_password = password
        self._password = generate_password_hash(password)

    @property
    def host_password(self):
        global encrypt_dict
        return decode(encrypt_dict, self._host_password)

    @host_password.setter
    def host_password(self, value):
        global encrypt_dict
        self._host_password = encode(encrypt_dict, value)

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
        
        db_session = DBSession()
        
        # Authenticate with LDAP Server first
        system_option = SystemOption.get(db_session)
        ldap_authenticated = False

        try:
            if system_option.enable_ldap_auth and not is_empty(username) and not is_empty(password):
                ldap_authenticated = ldap_auth(system_option, username, password)
        except CSMLDAPException:
            # logger.exception("authenticate hit exception")
            pass
        
        user = query(cls).filter(cls.username == username).first()
        if ldap_authenticated:
            if user is None:
                # Create a LDAP user with Network Administrator privilege
                user = create_user(db_session, username, password, UserPrivilege.NETWORK_ADMIN, username, username)
                return user, True
            else:
                # Update the password
                if not is_empty(password):
                    user.password = password
                    db_session.commit()
            
        if user is None:
            return None, False
        
        if not user.active:
            return user, False

        authenticated = user.check_password(password)

        # This is for backward compatibility.  Existing users before the feature "Use CSM Server User Credential"
        # will need to have their password encrypted for device installation authentication.
        if authenticated and is_empty(user.host_password):
            user.host_password = password
            db_session.commit()

        return user, user.check_password(password)
    
    @staticmethod
    def verify_auth_token(token):
        s = Serializer('CSMSERVER')
        db_session = DBSession()
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None    # valid token, but expired
        except BadSignature:
            return None    # invalid token

        user = db_session.query(User).filter(User.id == data['id']).first()
        return user

    def generate_auth_token(self, expiration=600):
        s = Serializer('CSMSERVER', expires_in=expiration)
        return s.dumps({'id': self.id})
    
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
    family = Column(String(20), default=UNKNOWN)
    platform = Column(String(20), default=UNKNOWN)
    software_platform = Column(String(20), default=UNKNOWN)
    software_version = Column(String(20), default=UNKNOWN)
    os_type = Column(String(20), default=UNKNOWN)
    location = Column(String(100))
    roles = Column(String(100))
    region_id = Column(Integer, ForeignKey('region.id'))
    proxy_agent = Column(String(30), default=ProxyAgent.CSM_SERVER)
    can_schedule = Column(Boolean, default=True)
    can_install = Column(Boolean, default=True)
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))

    region = relationship('Region', foreign_keys='Host.region_id') 

    context = relationship("HostContext",
                           cascade="all, delete-orphan")

    connection_param = relationship("ConnectionParam",
                                    order_by="ConnectionParam.id",
                                    backref="host",
                                    cascade="all, delete-orphan")

    host_inventory = relationship("HostInventory",
                                  order_by="HostInventory.id",
                                  cascade="all, delete-orphan")

    inventory = relationship("Inventory")

    inventory_job = relationship("InventoryJob",
                                 cascade="all, delete-orphan")
    
    inventory_job_history = relationship("InventoryJobHistory",
                                         order_by="desc(InventoryJobHistory.created_time)",
                                         backref="host",
                                         cascade="all, delete-orphan")
    
    packages = relationship("Package",
                            order_by="Package.id",
                            backref="host",
                            cascade="all, delete-orphan")
    
    install_job = relationship("InstallJob",
                               order_by="asc(InstallJob.scheduled_time)",
                               backref="host",
                               cascade="all, delete-orphan")
    
    install_job_history = relationship("InstallJobHistory",
                                       order_by="desc(InstallJobHistory.created_time)",
                                       backref="host",
                                       cascade="all, delete-orphan")

    UDIs = relationship("UDI",
                        order_by="asc(UDI.name)",
                        backref="host",
                        cascade="all, delete-orphan")

    def delete(self, db_session):
        """
        Delete host inventory job session logs
        Delete host install job session logs
        Update Inventory table accordingly
        Delete this host
        """
        for inventory_job in self.inventory_job_history:
            try:
                shutil.rmtree(os.path.join(get_log_directory(), inventory_job.session_log))
            except:
                logger.exception('hit exception when deleting host inventory job session logs')

        for install_job in self.install_job_history:
            try:
                shutil.rmtree(os.path.join(get_log_directory(), install_job.session_log))
            except:
                logger.exception('hit exception when deleting host install job session logs')

        for inventory in self.inventory:
            inventory.update(db_session, host_id=None, changed_time=datetime.datetime.utcnow())

        db_session.delete(self)

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
            logger.exception('Host.get_json() hit exception')
              
        return result


class HostContext(Base):
    __tablename__ = 'host_context'

    id = Column(Integer, primary_key=True)
    data = Column(JSONEncodedDict, default={})
    host_id = Column(Integer, ForeignKey('host.id'), unique=True)
    modified_time = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class ConnectionParam(Base):
    __tablename__ = 'connection_param'
    
    id = Column(Integer, primary_key=True)
    # Multiple IPs can be specified using comma as the delimiter
    host_or_ip = Column(String(100), nullable=False)
    username = Column(String(50), nullable=False)
    _password = Column('password', String(100), nullable=False)
    connection_type = Column(String(10), nullable=False)
    # Multiple Ports can be specified using comma as the delimiter
    port_number = Column(String(100), default='')

    # For IOS type devices
    _enable_password = Column('enable_password', String(100), default='')
    
    host_id = Column(Integer, ForeignKey('host.id'))
    jump_host_id = Column(Integer, ForeignKey('jump_host.id'))
    jump_host = relationship("JumpHost", foreign_keys='ConnectionParam.jump_host_id')
    
    @property
    def password(self):
        global encrypt_dict
        return decode(encrypt_dict, self._password)
    
    @password.setter
    def password(self, value):
        global encrypt_dict
        self._password = encode(encrypt_dict, value)

    @property
    def enable_password(self):
        global encrypt_dict
        return decode(encrypt_dict, self._enable_password)

    @enable_password.setter
    def enable_password(self, value):
        global encrypt_dict
        self._enable_password = encode(encrypt_dict, value)


class UDI(Base):
    __tablename__ = 'udi'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    description = Column(String(100))
    pid = Column(String(30))
    vid = Column(String(10))
    sn = Column(String(30))

    host_id = Column(Integer, ForeignKey('host.id'))


class JumpHost(Base):
    __tablename__ = 'jump_host'
    
    id = Column(Integer, primary_key=True)
    hostname = Column(String(100), nullable=False, index=True)
    host_or_ip = Column(String(50), nullable=False)
    username = Column(String(50), nullable=False)
    _password = Column('password', String(100), nullable=False)
    connection_type = Column(String(10), nullable=False)
    port_number = Column(String(10), default='')
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


class BaseModel(Base):
    __abstract__ = True

    # db_session needed for child class update method.
    # signature conformance here
    def update(self, db_session, **data):
        for key, value in data.iteritems():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                continue


class HostInventory(BaseModel):
    __tablename__ = 'host_inventory'
    id = Column(Integer, primary_key=True)

    host_id = Column(Integer, ForeignKey('host.id'), index=True)

    # Entity to parent : many to one
    parent_id = Column(Integer, ForeignKey(id), index=True)

    position = Column(Integer)

    location = Column(String(50))
    model_name = Column(String(50))
    name = Column(String(100))
    description = Column(String(200))
    serial_number = Column(String(50), index=True)
    hardware_revision = Column(String(10))
    # type = Column(String(50))
    # level = Column(Integer)  - for join operations

    children = relationship("HostInventory",

                            # many to one based on parent_id
                            backref=backref("parent", remote_side=id),

                            # cascade deletions
                            cascade="all, delete-orphan"
                            )

    def __init__(self, db_session, host_id=None, location="", model_name="", hardware_revision="",
                 name="", parent=None, serial_number="", description="", position=-1):
        self.host_id = host_id
        self.location = location
        self.model_name = model_name
        self.hardware_revision = hardware_revision
        self.name = name
        self.parent = parent
        self.serial_number = serial_number
        self.description = description
        self.position = position
        self.update_inventory(db_session)

    def update(self, db_session, **data):
        super(HostInventory, self).update(db_session, **data)
        self.update_inventory(db_session)

    def delete(self, db_session):
        """ Update Inventory table accordingly when deleting this HostInventory"""
        inventory = db_session.query(Inventory).filter(and_(Inventory.serial_number == self.serial_number,
                                                            Inventory.host_id == self.host_id)).first()
        if inventory:
            inventory.update(db_session, host_id=None, changed_time=datetime.datetime.utcnow())
        db_session.delete(self)

    def update_inventory(self, db_session):
        """ Update Inventory table accordingly when updating/creating this HostInventory"""
        inventory = db_session.query(Inventory).filter(Inventory.serial_number == self.serial_number).first()
        if inventory:
            # update only when there is actual update! - If there is a discrepancy with existing inventory data
            if not inventory.attributes_equal_to(host_id=self.host_id,
                                                 model_name=self.model_name,
                                                 description=self.description,
                                                 hardware_revision=self.hardware_revision):
                inventory.update(db_session, host_id=self.host_id, model_name=self.model_name,
                                 description=self.description, hardware_revision=self.hardware_revision,
                                 changed_time=datetime.datetime.utcnow())
        # check that serial_number is not None or "" just to be explicit here
        elif self.serial_number:
            inv = Inventory(serial_number=self.serial_number, host_id=self.host_id, model_name=self.model_name,
                            description=self.description, hardware_revision=self.hardware_revision)
            db_session.add(inv)


class Inventory(BaseModel):
    __tablename__ = 'inventory'

    serial_number = Column(String(50), primary_key=True)

    host_id = Column(Integer, ForeignKey('host.id'), index=True)

    model_name = Column(String(50))
    description = Column(String(200))
    hardware_revision = Column(String(10))

    notes = Column(Text)
    changed_time = Column(DateTime, default=datetime.datetime.utcnow)

    def __init__(self, serial_number="", host_id=None, model_name="", description="",
                 hardware_revision="", notes=""):
        if not serial_number:
            return
        self.serial_number = serial_number
        self.host_id = host_id
        self.model_name = model_name
        self.description = description
        self.hardware_revision = hardware_revision
        self.notes = notes

    def attributes_equal_to(self, **data):
        for key, value in data.iteritems():
            if hasattr(self, key):
                if getattr(self, key) != value:
                    return False
            else:
                continue
        return True


class HostInventoryHistory(BaseModel):
    __tablename__ = 'host_inventory_history'
    id = Column(Integer, primary_key=True)

    host_id = Column(Integer, ForeignKey('host.id'), index=True)

    notes = Column(Text)
    changed_time = Column(DateTime, default=datetime.datetime.utcnow)


class InventoryJob(Base):
    __tablename__ = 'inventory_job'
    
    id = Column(Integer, primary_key=True)
    request_update = Column(Boolean, default=True)
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
                                         cascade="all, delete-orphan")


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
    custom_command_profile_id = Column(String(20))

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
    vrf = Column(String(100))
    username = Column(String(100))
    _password = Column('password', String(100))
    server_directory = Column(String(100))
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
    
    regions = relationship('Region', order_by="Region.name", secondary=lambda: RegionServer)
    
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
                     Column('server_id', Integer, ForeignKey("server.id"), primary_key=True))


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


class CCOCatalog(Base):
    __tablename__ = 'cco_catalog'
    
    platform = Column(String(40), primary_key=True)
    release = Column(String(40), primary_key=True)


class SMUMeta(Base):
    __tablename__ = 'smu_meta'
    # name is like asr9k_px_4.2.3
    platform_release = Column(String(40), primary_key=True)
    created_time = Column(String(30)) # Use string instead of timestamp
    smu_software_type_id = Column(String(20))
    sp_software_type_id = Column(String(20))
    tar_software_type_id = Column(String(20))
    file_suffix = Column(String(10))
    pid = Column(String(200))
    mdf_id = Column(String(200))
    retrieval_time = Column(DateTime)

    smu_info = relationship("SMUInfo",
                            backref="smu_meta",
                            cascade="all, delete-orphan")


class SMUInfo(Base):
    __tablename__ = 'smu_info'

    id = Column(String(100), primary_key=True)
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
    compressed_image_size = Column(String(20))
    uncompressed_image_size = Column(String(20))
    
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
    schema_version = Column(Integer, default=CURRENT_SCHEMA_VERSION)
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
    install_history_per_host = Column(Integer, default=100)
    total_system_logs = Column(Integer, default=2000)
    enable_default_host_authentication = Column(Boolean, default=False)
    default_host_username = Column(String(50))
    _default_host_password = Column('default_host_password', String(100))
    default_host_authentication_choice = Column(String(10), default="1")
    base_url = Column(String(100))
    enable_ldap_auth = Column(Boolean, default=False)
    enable_ldap_host_auth = Column(Boolean, default=False)
    ldap_server_url = Column(String(100))
    enable_cco_lookup = Column(Boolean, default=True)
    cco_lookup_time = Column(DateTime)
    enable_user_credential_for_host = Column(Boolean, default=False)
    use_utc_timezone = Column(Boolean, default=False)
    
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
    string1 = Column(String(100), default=STRING1)
    string2 = Column(String(100), default=STRING2)
    
    @classmethod
    def get(cls, db_session):
        return db_session.query(Encrypt).first()


class Log(Base):
    __tablename__ = 'log'
    
    id = Column(Integer, primary_key=True)
    level = Column(String(20))
    trace = Column(Text)
    msg = Column(Text)
    created_time = Column(DateTime)


class CSMMessage(Base):
    __tablename__ = 'csm_message'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    acknowledgment_date = Column(DateTime)


class SoftwareProfile(Base):
    __tablename__ = 'software_profile'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    packages = Column(Text)
    created_by = Column(String(50))


class ConformanceReport(Base):
    __tablename__ = 'conformance_report'

    id = Column(Integer, primary_key=True)
    software_profile = Column(String(100))
    software_profile_packages = Column(Text)
    match_criteria = Column(String(30))
    hostnames = Column(Text)
    host_not_in_conformance = Column(Integer, default=0)
    host_out_dated_inventory = Column(Integer, default=0)
    created_time = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(50))
    user_id = Column(Integer, ForeignKey('user.id'))

    entries = relationship("ConformanceReportEntry",
                           order_by="ConformanceReportEntry.hostname",
                           backref="conformance_report",
                           cascade="all, delete-orphan")


class ConformanceReportEntry(Base):
    __tablename__ = 'conformance_report_entry'

    id = Column(Integer, primary_key=True)
    hostname = Column(String(50))
    platform = Column(String(20))
    software = Column(String(20))
    host_packages = Column(Text)
    missing_packages = Column(Text)
    conformed = Column(String(3))
    comments = Column(String(50))

    conformance_report_id = Column(Integer, ForeignKey('conformance_report.id'))


class EmailJob(Base):
    __tablename__ = 'email_job'

    id = Column(Integer, primary_key=True)
    recipients = Column(String(200))
    message = Column(Text)
    scheduled_time = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(200))
    status_time = Column(DateTime)
    created_by = Column(String(50))

    def set_status(self, status):
        self.status = status
        self.status_time = datetime.datetime.utcnow()

class CreateTarJob(Base):
    __tablename__ = 'create_tar_job'

    id = Column(Integer, primary_key=True)
    server_id = Column(Integer)
    server_directory = Column(String(300))
    source_tars = Column(Text)
    contents = Column(Text)
    additional_packages = Column(Text)
    new_tar_name = Column(String(50))
    status = Column(String(200))
    status_time = Column(DateTime)
    created_by = Column(String(50))

    def set_status(self, status):
        self.status = status
        self.status_time = datetime.datetime.utcnow()


class ConvertConfigJob(Base):
    __tablename__ = 'convert_config_job'

    id = Column(Integer, primary_key=True)
    file_path = Column(String(200))
    status = Column(String(200))
    status_time = Column(DateTime)

    def set_status(self, status):
        self.status = status
        self.status_time = datetime.datetime.utcnow()


class CustomCommandProfile(Base):
    __tablename__ = 'custom_command_profile'

    id = Column(Integer, primary_key=True)
    profile_name = Column(String(100))
    command_list = Column(Text)
    created_by = Column(String(50))


class System(Base):
    __tablename__ = 'system'

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, default=datetime.datetime.utcnow())


Base.metadata.create_all(engine)


class LogHandler(logging.Handler):

    def __init__(self, db_session):
        logging.Handler.__init__(self)
        self.db_session = db_session

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

        self.db_session.add(log)
        self.db_session.commit()
        
logger = logging.getLogger('logger')
logger.setLevel(logging.DEBUG)
logger.addHandler(LogHandler(DBSession()))


def get_db_session_logger(db_session):
    """
    Return a session specific logger.  This is necessary especially
    if the db_session is from a different process address space.
    """
    session_logger = logging.getLogger('session_logger_%s' % db_session.hash_key)
    if not hasattr(session_logger, 'initialized'):
        session_logger.setLevel(logging.DEBUG)
        session_logger.addHandler(LogHandler(db_session))
        session_logger.initialized = True

    return session_logger

       
def get_download_job_key_dict():
    result = {}
    db_session = DBSession()
    download_jobs = db_session.query(DownloadJob).all()
    for download_job in download_jobs:
        download_job_key = "{}{}{}{}".format(download_job.user_id,download_job.cco_filename,
                                             download_job.server_id, download_job.server_directory)
        result[download_job_key] = download_job
    return result


def init_system_version():
    db_session = DBSession()
    if db_session.query(SystemVersion).count() == 0:
        db_session.add(SystemVersion())
        db_session.commit()


def create_user(db_session, username, password, privilege, fullname, email):
    user = User(
        username=username,
        password=password,
        privilege=privilege,
        fullname=fullname,
        email=email)
    user.preferences.append(Preferences())
    db_session.add(user)
    db_session.commit()
    
    return user


def init_user():
    db_session = DBSession()

    # Setup a default cisco user if none exists
    if db_session.query(User).count() == 0:
        create_user(db_session, 'root', 'root', UserPrivilege.ADMIN, 'admin', 'admin')


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


def init_sys_time():
    db_session = DBSession()
    if db_session.query(System).count() == 0:
        db_session.add(System())
        db_session.commit()
    else:
        system = db_session.query(System).first()
        system.start_time = datetime.datetime.utcnow()
        db_session.commit()


def initialize():
    init_user()      
    init_system_option()
    init_sys_time()


init_system_version()
init_encrypt() 
 
if __name__ == '__main__':
    pass
