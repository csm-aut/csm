from models import SystemOption
from database import DBSession

class BaseMigrate(object):
    def __init__(self, version):
        self.version = version

    def update_schema_version(self):
        db_session = DBSession()
        system_option = SystemOption.get(db_session)
        system_option.schema_version = self.version
        db_session.commit()

    def execute(self):
        self.start()
        self.update_schema_version()

    def start(self):       
        raise NotImplementedError("Children must override start")
