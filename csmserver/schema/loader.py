from utils import import_class

def get_schema_migrate_class(version):
    return import_class('schema.migrate_to_version_%s.SchemaMigrate' % version)
