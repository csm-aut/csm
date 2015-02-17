from parsers.platforms.iosxr import BaseCLIPackageParser 

class CLIPackageParser(BaseCLIPackageParser):
    def get_packages_from_cli(self, ctx, install_inactive_cli=None, install_active_cli=None, install_committed_cli=None):
        return super(CLIPackageParser, self).get_packages_from_cli(ctx, install_inactive_cli, install_active_cli, install_committed_cli)
