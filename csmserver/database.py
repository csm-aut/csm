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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.engine.url import URL

from salts import encode, decode
from utils import import_module

from constants import get_csm_data_directory
import os

# DO NOT MODIFY THESE STRINGS.  THEY ARE USED FOR ENCRYPTION.
STRING1 = "ABCDEF~!@#$%^&*()-_=+|[]{};:',.<>asdfghj/?GHIJKLMNOPQRSTUVWXYZ12345qwertyuiopkl67890zxcvbnm"
STRING2 = "WERTY[}{|=+-_)~abcdenojk54321ZpASstuUI09876OP/?.,<>';:]QfghiXCVBNMlmvwDFGHJKL(*&^%$#@!qrxyz"

PREFIX = 'encrypted'
ENCRYPT = {'key': 'csmserver', 'string1': STRING1, 'string2': STRING2}

# Make sure the CURRENT_SCHEMA_VERSION is an integer
CURRENT_SCHEMA_VERSION = 5
ENABLE_DEBUG = False


def create_database_if_not_exists(db_settings):
    """
    Creates the database if it has not been created yet.
    """
    # Make a deep copy of the db_settings

    drivername = db_settings['drivername']
    if 'pymysql' in drivername:
        db_dict = dict(db_settings)
        del db_dict['database']
        engine = create_engine(URL(**db_dict))
        engine.execute("create database if not exists " + db_settings['database'])


def get_database_settings():
    """
    An example content of database.ini

    For MySQL.

    [Database]
    drivername: mysql+pymysql
    host: localhost
    port: 3306
    username: root
    password: root
    database: csmdb

    For PostgreSQL

    [Database]
    drivername: postgresql+psycopg2
    host: localhost
    port: 5432
    username: root
    password: root
    database: csmdb

    The username and password in database.ini will be encrypted
    if it is not already in encrypted format.
    """
    global ENABLE_DEBUG
    
    # Python 2.7.6, ConfigParser, Python 3.3, configparser
    module = import_module('ConfigParser')
    if module is None:
        module = import_module('configparser')
        
    config = module.RawConfigParser()

    # The database.ini should be in the csm_data directory which should be at the same level as the csm directory.
    config.read(os.path.join(os.getcwd(), 'database.ini'))
    # config.read(os.path.join(get_csm_data_directory(), 'database.ini'))

    db_dict = dict(config.items('Database'))
    username = decode(ENCRYPT, db_dict['username'])
    password = decode(ENCRYPT, db_dict['password'])

    # If the username/password have not been encrypted, encrypt them
    if username.find(PREFIX) == -1 and password.find(PREFIX) == -1:
        config.set('Database', 'username', encode(ENCRYPT, PREFIX + db_dict['username']))
        config.set('Database', 'password', encode(ENCRYPT, PREFIX + db_dict['password']))
        
        with open('database.ini', 'w') as config_file:
            config.write(config_file)
      
    else:
        db_dict['username'] = username.replace(PREFIX, '')
        db_dict['password'] = password.replace(PREFIX, '')
        
    ENABLE_DEBUG = config.getboolean('Debug', 'debug')
    return db_dict

db_settings = get_database_settings()
create_database_if_not_exists(db_settings)

DATABASE_CONNECTION_INFO = URL(**db_settings)
# Create the database engine
engine = create_engine(DATABASE_CONNECTION_INFO, pool_size=20, pool_recycle=3600,
                       convert_unicode=True, echo=ENABLE_DEBUG)

DBSession = scoped_session(sessionmaker(autocommit=False,
                                        autoflush=False,
                                        bind=engine))

if __name__ == '__main__': 
    pass
