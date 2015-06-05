from models import logger
from models import SystemOption
from database import DBSession, CURRENT_SCHEMA_VERSION

from utils import create_directory
from constants import get_autlogs_directory, get_repository_directory, get_temp_directory
from schema.loader import get_schema_migrate_class

import traceback

# Create the necessary supporting directories
create_directory(get_autlogs_directory())
create_directory(get_repository_directory())
create_directory(get_temp_directory())

def main():
    db_session = DBSession()
    system_option = SystemOption.get(db_session)

    # Handles database schema migration
    for version in range(system_option.schema_version, CURRENT_SCHEMA_VERSION+1):    
        handler_class = get_schema_migrate_class(version)
        if handler_class is not None:
            try:
                handler_class(version).execute()
            except:
                print(traceback.format_exc())

if __name__ == '__main__':
    main()
