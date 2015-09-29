import re

def get_package(device):
    csm_ctx = device.get_property('ctx')
    if not csm_ctx:
        return


    asr9k_exr = False

    success, output = device.execute_command("admin")

    if success:

        success, output = device.execute_command("show install active")

        if success:

            module = None

            lines = output.splitlines()

            for line in lines:
                line = line.strip()
                if len(line) == 0:
                    continue
                m = re.match("Node.*", line)
                if m:
                    # Node 0/RP1/CPU0 [RP]
                    module = line.split()[1]
                else:
                    if module is not None:
                        match = re.search('asr9k-sysadmin', line)
                        if match:
                            asr9k_exr = True
                            break

            prefix = "admin " if not asr9k_exr else ""
            append = " summary" if not asr9k_exr else ""

            success, output = device.execute_command("exit")

            if success:

                if hasattr(csm_ctx, 'active_cli'):
                    success, output = device.execute_command(prefix + "show install active" + append)
                    if success:
                        csm_ctx.active_cli = output

                if hasattr(csm_ctx, 'inactive_cli'):
                    success, output = device.execute_command(prefix + "show install inactive" + append)
                    if success:
                        csm_ctx.inactive_cli = output

                if hasattr(csm_ctx, 'committed_cli'):
                    success, output = device.execute_command(prefix + "show install committed" + append)
                    if success:
                        csm_ctx.committed_cli = output

                return ""

            else:
                return "executing command 'exit' to exit admin mode failed. Please check session.log"

        else:
            return "executing command 'show install active' in admin mode failed. Please check session.log"



    else:

        return "executing command 'admin' to enter admin mode failed. Please check session.log"