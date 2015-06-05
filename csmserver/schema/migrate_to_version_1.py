from schema.base import BaseMigrate
from database import DBSession

class SchemaMigrate(BaseMigrate):
    def __init__(self, version):
        BaseMigrate.__init__(self, version)

    def start(self):
        try:
            db_session = DBSession()
            db_session.execute('alter table system_option add base_url VARCHAR(100)')
        except:
            pass 
