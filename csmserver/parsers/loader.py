from utils import import_class

def get_package_parser_class(target_platform):
    return import_class('parsers.platforms.%s.CLIPackageParser' % target_platform)

