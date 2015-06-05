from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.engine.url import URL

from salts import encode, decode
from utils import import_module
import os

# DO NOT MODIFY THESE STRINGS.  THEY ARE USED FOR ENCRYPTION.
STRING1 = "ABCDEF~!@#$%^&*()-_=+|[]{};:',.<>asdfghj/?GHIJKLMNOPQRSTUVWXYZ12345qwertyuiopkl67890zxcvbnm"
STRING2 = "WERTY[}{|=+-_)~abcdenojk54321ZpASstuUI09876OP/?.,<>';:]QfghiXCVBNMlmvwDFGHJKL(*&^%$#@!qrxyz"

PREFIX = 'encrypted'
ENCRYPT = {'key' : 'csmserver', 'string1' : STRING1, 'string2' : STRING2}

CURRENT_SCHEMA_VERSION = 1
ENABLE_DEBUG=False

"""
Creates the database if it has not been created yet.
"""
def create_database_if_not_exists(db_settings):
    # Make a deep copy of the db_settings

    drivername = db_settings['drivername']
    if 'pymysql' in drivername:
        db_dict = dict(db_settings)
        del db_dict['database']
        engine = create_engine(URL(**db_dict))
        engine.execute("create database if not exists " + db_settings['database'])
    
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
def get_database_settings():
    global ENABLE_DEBUG
    
    # Python 2.7.6, ConfigParser, Python 3.3, configparser
    module = import_module('ConfigParser')
    if module is None:
        module = import_module('configparser')
        
    config = module.RawConfigParser()  
    config.read(os.getcwd() + os.path.sep + 'database.ini')

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
engine = create_engine(DATABASE_CONNECTION_INFO, pool_size=20, pool_recycle=3600, convert_unicode=True, echo=ENABLE_DEBUG)
DBSession = scoped_session(sessionmaker(autocommit=False,
                                        autoflush=False,
                                        bind=engine))

if __name__ == '__main__': 
    pass
