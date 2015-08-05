def get_package(device, os):
    csm_ctx = device.get_property('ctx')
    if not csm_ctx :
        return
    device.execute_command("admin")
    append = " summary" if os == 'xr' else ""
    if hasattr(csm_ctx, 'active_cli'):
        success, output = device.execute_command("show install active" + append)
        if success:
            csm_ctx.active_cli = output

    if hasattr(csm_ctx, 'inactive_cli'):
        success, output = device.execute_command("show install inactive" + append)
        if success:
            csm_ctx.inactive_cli = output

    if hasattr(csm_ctx, 'committed_cli'):
        success, output = device.execute_command("show install committed" + append)
        if success:
            csm_ctx.committed_cli = output
    device.execute_command("exit")