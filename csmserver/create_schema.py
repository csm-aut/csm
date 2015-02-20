# This will force database creation for a new installation via a single entry point
# Otherwise, gunicorn multiple workers will create contention when they all start.
# See csmserver launch script
import models
