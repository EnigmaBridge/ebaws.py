from cmd2 import Cmd
import argparse
import sys
import os
import math
import types
import traceback
import pid
import time
import util
from consts import *
from core import Core
from registration import Registration
from softhsm import SoftHsmV1Config
from ejbca import Ejbca
from ebsysconfig import SysConfig
from letsencrypt import LetsEncrypt


class App(Cmd):
    """EnigmaBridge AWS command line interface"""
    prompt = '$> '
    intro = '-'*80 + '\n    Enigma Bridge AWS command line interface. ' \
                     '\n    For help, type usage\n' + \
                     '\n    init - initializes the EJBCA instance\n' + \
            '-'*80

    def __init__(self, *args, **kwargs):
        """
        Init core
        :param args:
        :param kwargs:
        :return:
        """
        Cmd.__init__(self, *args, **kwargs)
        self.core = Core()
        self.args = None

        self.noninteractive = False

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
        if not self.check_root() or not self.check_pid():
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
            syscfg = SysConfig(print_output=True)
            hostname = None

            # Determine if we have enough RAM for the work.
            # If not, a new swap file is created so the system has at least 2GB total memory space
            # for compilation & deployment.
            if not syscfg.is_enough_ram():
                total_mem = syscfg.get_total_usable_mem()
                print("\nTotal memory in the system is low: %d MB, installation requires at least 2GB"
                      % int(math.ceil(total_mem/1024/1024)))

                print("New swap file will be installed in /var")
                should_continue = self.ask_proceed()
                if not should_continue:
                    return

                code, swap_name, swap_size = syscfg.create_swap()
                if code == 0:
                    print("\nNew swap file was created %s %d MB and activated" % (swap_name,int(math.ceil(total_mem/1024/1024))))
                else:
                    print("\nSwap file could not be created. Please, inspect the problem and try again")
                    return

                # Recheck
                if not syscfg.is_enough_ram():
                    print("Error: still not enough memory. Please, resolve the issue and try again")
                    return
                print("")

            # Creates a new RSA key-pair identity
            # Identity relates to bound DNS names and username.
            # Requests for DNS manipulation need to be signed with the private key.
            reg_svc.new_identity(id_dir=CONFIG_DIR, backup_dir=CONFIG_DIR_OLD)

            # New client registration (new username, password, apikey).
            new_config = reg_svc.new_registration()

            # Assign a new dynamic domain for the host
            domain_is_ok = False
            domain_ignore = False
            domain_ctr = 0
            while not domain_is_ok and domain_ctr < 3:
                try:
                    new_config = reg_svc.new_domain()
                    new_config = reg_svc.refresh_domain()

                    if new_config.domains is not None and len(new_config.domains) > 0:
                        domain_is_ok = True
                        hostname = new_config.domains[0]
                        print("\nNew domains registered for this host: ")
                        for domain in new_config.domains:
                            print("  %s" % domain)
                        print("")

                except Exception as e:
                    domain_ctr += 1
                    print("\nError during domain registration, no dynamic domain will be assigned")
                    print("Do you want to try again?")
                    should_continue = self.ask_proceed()
                    if not should_continue:
                        break

            # Is it OK if domain assignment failed?
            if not domain_is_ok:
                if domain_ignore:
                    print("\nDomain could not be assigned, installation continues. You can try domain reassign later")
                else:
                    print("\nDomain could not be assigned, installation aborted")
                    return

            # Install to the OS
            syscfg.install_onboot_check()
            syscfg.install_cron_renew()

            # Dump config & SoftHSM
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
            print("SoftHSMv1 initialization: %s" % out)

            # EJBCA configuration
            print("Going to install EJBCA")
            print("  This may take 5-15 minutes, please, do not interrupt the installation")
            print("  and wait until the process completes.\n")

            ejbca.set_config(new_config)
            ejbca.set_hostname(hostname)
            ejbca.configure()

            if ejbca.ejbca_install_result != 0:
                print("\nEJBCA installation error, please, try again.")
                return

            Core.write_configuration(ejbca.config)
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

            # LetsEncrypt enrollment
            self.le_install(ejbca)

            # Finalize, P12 file & final instructions
            new_p12 = ejbca.copy_p12_file()
            print("\nDownload p12 file %s" % new_p12)
            print(" e.g.: scp %s:%s ." % (reg_svc.info_loader.ami_public_hostname, new_p12))
            print("Export password: %s" % ejbca.superadmin_pass)
            print("\nOnce you import p12 file to your browser you can connect to the admin interface at")
            if hostname is not None:
                print("https://%s:8443/ejbca/adminweb/" % hostname)
            print("https://%s:8443/ejbca/adminweb/" % reg_svc.info_loader.ami_public_hostname)

        except Exception as ex:
            traceback.print_exc()
            print "Exception in the registration process"

    def do_renew(self, arg):
        """Renews LetsEncrypt certificates used for the JBoss"""
        if not self.check_root() or not self.check_pid():
            return

        config = Core.read_configuration()
        if config is None or not config.has_nonempty_config():
            print "\nError! Enigma config file not found %s" % (Core.get_config_file_path())
            print " Cannot continue. Have you run init already?\n"
            return

        domains = config.domains
        if domains is None or not isinstance(domains, types.ListType) or len(domains) == 0:
            print "\nError! No domains found in the configuration."
            print " Cannot continue. Did init complete successfully?"
            return

        # If there is no hostname, enrollment probably failed.
        ejbca_host = config.ejbca_hostname
        ejbca = Ejbca(print_output=True, jks_pass=config.ejbca_jks_password, config=config, hostname=ejbca_host)

        le_test = LetsEncrypt()
        enroll_new_cert = ejbca_host is None or len(ejbca_host) == 0 or ejbca_host == 'localhost'

        if not enroll_new_cert:
            enroll_new_cert = le_test.is_certificate_ready(domain=ejbca_host) != 0
        else:
            ejbca_host = domains[0]
            ejbca.hostname = ejbca_host

        if enroll_new_cert:
            # Enroll a new certificate
            self.le_install(ejbca)
        else:
            # Renew the certs
            self.le_renew(ejbca)
        pass

    def do_onboot(self, line):
        """Command called by the init script/systemd on boot, takes care about IP re-registration"""
        pass

    def do_undeploy_ejbca(self, line):
        """Undeploys EJBCA without any backup left"""
        if not self.check_root() or not self.check_pid():
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

    def le_install(self, ejbca):
        print('\nInstalling LetsEncrypt certificate for: %s' % ejbca.hostname)
        ret = ejbca.le_enroll()
        if ret == 0:
            Core.write_configuration(ejbca.config)
            ejbca.jboss_reload()
            print('\nLetsEncrypt certificate installed')

        else:
            print('\nFailed to install LetsEncrypt certificate, code=%s.' % ret)
            print('You can try it again later with command renew\n')
        return ret

    def le_renew(self, ejbca):
        print('\nRenewing LetsEncrypt certificate for: %s' % ejbca.hostname)
        ret = ejbca.le_renew()
        if ret == 0:
            Core.write_configuration(ejbca.config)
            ejbca.jboss_reload()
            print('\nNew LetsEncrypt certificate installed')

        elif ret == 1:
            print('\nRenewal not needed, certificate did not change')

        else:
            print('\nFailed to renew LetsEncrypt certificate, code=%s.' % ret)
            print('You can try it again later with command renew\n')
        return ret

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
            elif not util.safe_email(var):
                print('Email you have entered is invalid, try again')
                continue
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

    def check_pid(self, retry=True):
        """Checks if the tool is running"""
        first_retry = True
        attempt_ctr = 0
        while first_retry or retry:
            try:
                first_retry = False
                attempt_ctr += 1
                self.core.pidlock_create()
                if attempt_ctr > 1:
                    print("\nPID lock acquired")
                return True

            except pid.PidFileAlreadyRunningError as e:
                return True

            except pid.PidFileError as e:
                pidnum = self.core.pidlock_get_pid()
                print("\nError: CLI already running in exclusive mode by PID: %d" % pidnum)
                print("Next check will be performed in few seconds. Waiting...")
                time.sleep(3)
        pass

    def app_main(self):
        # Backup original arguments for later parsing
        args_src = sys.argv

        # Parse our argument list
        parser = argparse.ArgumentParser(description='EnigmaBridge AWS client')
        parser.add_argument('-n, --non-interactive', dest='noninteractive', action='store_const', const=True,
                            help='non-interactive mode of operation, command line only')

        parser.add_argument('commands', nargs=argparse.ZERO_OR_MORE, default=[],
                            help='commands to process')

        self.args = parser.parse_args(args=args_src[1:])
        self.noninteractive = self.args.noninteractive

        # Fixing cmd2 arg parsing, call cmdLoop
        sys.argv = [args_src[0]]
        for cmd in self.args.commands:
            sys.argv.append(cmd)

        # Terminate after execution is over on the non-interactive mode
        if self.noninteractive:
            sys.argv.append('quit')

        self.cmdloop()
        sys.argv = args_src


def main():
    app = App()
    app.app_main()


if __name__ == '__main__':
    main()
