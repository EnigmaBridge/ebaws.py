from cmd2 import Cmd
import argparse
import sys
import os
from core import Core
from registration import Registration
from softhsm import SoftHsmV1Config
from ejbca import Ejbca
import traceback


class App(Cmd):
    """EnigmaBridge AWS command line interface"""
    prompt = '$> '
    intro = '-'*80 + '\n    Enigma Bridge AWS command line interface. ' \
                     '\n    For help, type usage\n' + \
                     '\n    init - initializes the EJBCA instance\n' + \
            '-'*80

    def do_dump_config(self, line):
        """Dumps the current configuration to the terminal"""
        config = Core.read_configuration()
        print(config.to_string())

    def do_usage(self, line):
        """Writes simple usage hints"""
        print('init  - initializes the EJBCA instance with new identity')
        print('usage - writes this usage info')

    def do_init(self, line):
        """
        Initializes the EB client machine, new identity is assigned.
         - New EnigmaBridge identity is fetched
         - EnigmaBridge PKCS#11 Proxy is configured, new token is initialized
         - EJBCA is reinstalled with PKCS#11 support, with new certificates
        Previous configuration data is backed up.
        """
        if not self.check_root():
            return

        print "Going to initialize the EB identity"
        print "WARNING! This is a destructive process!"
        print "WARNING! The previous installation will be overwritten.\n"
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
            soft_config = SoftHsmV1Config()
            ejbca = Ejbca(print_output=True)

            # New client registration.
            new_config = reg_svc.new_registration()
            conf_file = Core.write_configuration(new_config)
            print("New configuration was written to: %s\n" % conf_file)

            # SoftHSMv1 reconfigure
            soft_config_backup_location = soft_config.backup_current_config_file()
            print("SoftHSMv1 configuration has been backed up to: %s" % soft_config_backup_location)

            soft_config.configure(new_config)
            soft_config_file = soft_config.write_config()

            print("New SoftHSMv1 configuration has been written to: %s\n" % soft_config_file)

            # Init the token
            backup_dir = soft_config.backup_previous_token_dir()
            if backup_dir is not None:
                print("SoftHSMv1 previous token database moved to: %s" % backup_dir)

            out, err = soft_config.init_token(user=ejbca.JBOSS_USER)
            print("SoftHSMv1 initialization: %s\n" % out)

            # EJBCA configuration
            print("Going to install EJBCA")
            print("  This may take 5-15 minutes, please, do not interrupt the installation")
            print("  and wait until the process completes.\n")
            ejbca.configure()
            if ejbca.ejbca_install_result != 0:
                print("\nEJBCA installation error, please, try again.")
                return
            print("\nEJBCA installed successfully.")

            # Generate new keys
            print('\nGoing to generate EnigmaBridge keys in the crypto token:')
            ret, out, err = ejbca.pkcs11_generate_default_key_set(softhsm=soft_config)
            key_gen_cmds = [
                    ejbca.pkcs11_get_generate_key_cmd(softhsm=soft_config, bit_size=2048, alias='signKey', slot_id=0),
                    ejbca.pkcs11_get_generate_key_cmd(softhsm=soft_config, bit_size=2048, alias='defaultKey', slot_id=0),
                    ejbca.pkcs11_get_generate_key_cmd(softhsm=soft_config, bit_size=1024, alias='testKey', slot_id=0)
                ]

            if ret != 0:
                print('\nError generating a new keys')
                print('You can do it later manually by calling')

                for tmpcmd in key_gen_cmds:
                    print('  %s' % ejbca.pkcs11_get_command(tmpcmd))

                print('Error from the command:')
                print(''.join(out))
                print(''.join(err))
            else:
                print('\nEnigmaBridge tokens generated successfully')
                print('You can use these newly generated keys for your CA or generate another ones with:')
                for tmpcmd in key_gen_cmds:
                    print('  %s' % ejbca.pkcs11_get_command(tmpcmd))

            # Add SoftHSM crypto token to EJBCA
            print('\nAdding EnigmaBridge crypto token to EJBCA:')
            ret, out, err = ejbca.ejbca_add_softhsm_token(softhsm=soft_config, name='EnigmaBridgeToken')
            if ret != 0:
                print('\nError in adding EnigmaBridge token to the EJBCA')
                print('You can add it manually in the EJBCA admin page later')
                print('Pin for the SoftHSMv1 (EnigmaBridge) token is 0000')
            else:
                print('\nEnigmaBridgeToken added to EJBCA')

            # Finalize, P12 file & final instructions
            new_p12 = ejbca.copy_p12_file()
            print("\nDownload p12 file %s" % new_p12)
            print(" e.g.: scp %s:%s ." % (reg_svc.info_loader.ami_public_hostname, new_p12))
            print("Export password: %s" % ejbca.superadmin_pass)
            print("\nOnce you import p12 file to your browser you can connect to the admin interface at")
            print("https://%s:8443/ejbca/adminweb/" % reg_svc.info_loader.ami_public_hostname)

        except Exception as ex:
            traceback.print_exc()
            print "Exception in the registration process"

    def do_undeploy_ejbca(self, line):
        """Undeploys EJBCA without any backup left"""
        if not self.check_root():
            return

        print "Going to undeploy and remove EJBCA from the system"
        print "WARNING! This is a destructive process!"
        should_continue = self.ask_proceed()
        if not should_continue:
            return

        print "WARNING! This is the last chance."
        should_continue = self.ask_proceed()
        if not should_continue:
            return

        ejbca = Ejbca(print_output=True)

        print " - Undeploying EJBCA from JBoss"
        ejbca.undeploy()
        ejbca.jboss_restart()

        print "\nDone."

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

    def check_root(self):
        """Checks if the script was started with root - we need that for file ops :/"""
        uid = os.getuid()
        euid = os.geteuid()
        if uid != 0 and euid != 0:
            print("Error: This action requires root privileges")
            print("Please, start the client with: sudo -E -H ebaws")
            return False
        return True

    def do_EOF(self, line):
        return True


def main():
    App().cmdloop()


if __name__ == '__main__':
    main()
