from cmd2 import Cmd
import argparse
from core import Core
from registration import Registration
from softhsm_config import SoftHsmV1Config
from ejbca import Ejbca
import traceback


class App(Cmd):
    """EnigmaBridge AWS command line interface"""
    prompt = '$> '
    intro = '-'*80 + '\n    Enigma Bridge AWS command line interface. ' \
                     '\n    For help, type ?\n' + \
            '-'*80

    def do_dump_config(self, line):
        """Dumps the current configuration to the terminal"""
        config = Core.read_configuration()
        print(config.to_string())

    def do_init(self, line):
        """Initializes the EB client machine, new identity is assigned."""
        print "Going to initialize the EB identity"
        print "WARNING! This is a destructive process!\n"
        should_continue = self.ask_proceed()
        if not should_continue:
            return

        config = Core.read_configuration()
        if config is not None and config.has_nonempty_config():
            print "\nWARNING! Configuration already exists in the file %s" % (Core.get_config_file_path())
            print "The configuration will be overwritten by a new one (current config will be backed up)\n"
            should_continue = self.ask_proceed()
            if not should_continue:
                return

            # Backup the old config
            fname = Core.backup_configuration(config)
            print("Configuration has been backed up: %s\n" % fname)

        # Reinit
        email = self.ask_for_email()
        eb_cfg = Core.get_default_eb_config()
        try:
            reg_svc = Registration(email=email, eb_cfg=eb_cfg)
            new_config = reg_svc.new_registration()
            conf_file = Core.write_configuration(new_config)
            print("New configuration was written to: %s\n" % conf_file)

            # SoftHSMv1 reconfigure
            soft_config = SoftHsmV1Config()
            soft_config_backup_location = soft_config.backup_current_config_file()
            print("SoftHSMv1 configuration has been backed up to: %s" % soft_config_backup_location)

            soft_config.configure(new_config)
            soft_config_file = soft_config.write_config()

            print("New SoftHSMv1 configuration has been written to: %s\n" % soft_config_file)

            # Init the token
            backup_dir = soft_config.backup_previous_token_dir()
            if backup_dir is not None:
                print("SoftHSMv1 previous token database moved to: %s" % backup_dir)

            out, err = soft_config.init_token()
            print("SoftHSMv1 initialization: %s\n" % out)

            # EJBCA configuration
            ejbca = Ejbca()

            # TODO: configure EJBCA, restart, ...
            # TODO: show user where to get p12 file


        except Exception as ex:
            traceback.print_exc()
            print "Exception in the registration process"

    def ask_proceed(self, question=None):
        """Ask if user wants to proceed"""
        confirmation = None
        while confirmation != 'y' and confirmation != 'n':
            confirmation = raw_input(question if question is not None else "Do you really want to proceed? (Y/n): ").strip().lower()

        return confirmation == 'y'

    def ask_for_email(self):
        """Asks user for an email address"""
        confirmation = False
        var = None

        while not confirmation:
            var = raw_input("Please enter your email address [empty]: ").strip()
            question = None
            if len(var) == 0:
                question = "You have entered an empty email address, is it correct? (Y/n):"
            else:
                question = "Is this email correct? \"%s\" (Y/n):" % var
            confirmation = self.ask_proceed(question)
        return var

    def do_EOF(self, line):
        return True


if __name__ == '__main__':
    App().cmdloop()
