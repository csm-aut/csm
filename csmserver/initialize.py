# By importing models here, it forces creation of tables in the database for a new installation.
# This will prevent gunicorn workers from trying to create the database tables all at the same time. 
# See csmserver launch script
import models

from utils import create_directory
from constants import get_autlogs_directory, get_repository_directory, get_temp_directory

# Create the necessary supporting directories
create_directory(get_autlogs_directory())
create_directory(get_repository_directory())
create_directory(get_temp_directory())

