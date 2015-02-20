from handlers.platforms.iosxr import BaseConnectionHandler, BaseInventoryHandler, BaseInstallHandler

class ConnectionHandler(BaseConnectionHandler):
    def execute(self, ctx):
        return super(ConnectionHandler, self).execute(ctx)
    
class InventoryHandler(BaseInventoryHandler):
    def execute(self, ctx):
        return super(InventoryHandler, self).execute(ctx)
    
class InstallHandler(BaseInstallHandler):
    def execute(self, ctx):
        return super(InstallHandler, self).execute(ctx)