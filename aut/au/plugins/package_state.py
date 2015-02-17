def get_package(device):
    csm_ctx = device.get_property('ctx')
    if not csm_ctx :
        return
    if hasattr(csm_ctx, 'active_cli'):
        success, output = device.execute_command( "admin show install active summary")
        if success:
            csm_ctx.active_cli = output
    if hasattr(csm_ctx, 'inactive_cli'):
        success, output = device.execute_command( "admin show install inactive summary")
        if success:
            csm_ctx.inactive_cli = output
    if hasattr(csm_ctx, 'committed_cli'):
        success, output = device.execute_command( "admin show install committed summary")
        if success:
            csm_ctx.committed_cli = output
