from utils import import_class

def get_connection_handler_class(target_platform):
    return import_class('handlers.platforms.%s.ConnectionHandler' % target_platform)

def get_inventory_handler_class(target_platform):
    return import_class('handlers.platforms.%s.InventoryHandler' % target_platform)

def get_install_handler_class(target_platform):
    return import_class('handlers.platforms.%s.InstallHandler' % target_platform)
