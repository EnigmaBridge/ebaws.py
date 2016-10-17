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
import errors
import textwrap
from blessed import Terminal
from consts import *
from core import Core
from registration import Registration, InfoLoader
from softhsm import SoftHsmV1Config
from ejbca import Ejbca
from ebsysconfig import SysConfig
from letsencrypt import LetsEncrypt
from pkg_resources import get_distribution, DistributionNotFound


class App(Cmd):
    """EnigmaBridge AWS command line interface"""
    prompt = '$> '

    PIP_NAME = 'ebaws.py'
    PROCEED_YES = 'yes'
    PROCEED_NO = 'no'
    PROCEED_QUIT = 'quit'

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
        self.last_result = 0

        self.noninteractive = False
        self.version = self.load_version()
        self.first_run = self.is_first_run()

        self.t = Terminal()
        self.update_intro()

    def load_version(self):
        dist = None
        version = None
        try:
            dist = get_distribution(self.PIP_NAME)
            dist_loc = os.path.normcase(dist.location)
            here = os.path.normcase(__file__)
            if not here.startswith(dist_loc):
                raise DistributionNotFound
            else:
                version = dist.version
        except:
            version = 'Trunk'
        return version

    def is_first_run(self):
        try:
            config = Core.read_configuration()
            return config is None or config.has_nonempty_config()
        except:
            return True

    def update_intro(self):
        self.intro = '-'*self.get_term_width() + \
                     ('\n    Enigma Bridge AWS command line interface (v%s) \n' % self.version) + \
                     '\n    usage - shows simple command list' + \
                     '\n    init  - initializes the key management system\n'

        if self.first_run:
            self.intro += '            run this when running for the first time\n'

        self.intro += '\n    More info: https://enigmabridge.com/amazonpki \n' + \
                     '-'*self.get_term_width()

    def do_version(self, line):
        print('%s-%s' % (self.PIP_NAME, self.version))

    def do_dump_config(self, line):
        """Dumps the current configuration to the terminal"""
        config = Core.read_configuration()
        if config is None:
            print('None configuration is stored.')
            print('init was probably not called on this machine.')
        else:
            print(config.to_string())

    def do_usage(self, line):
        """Writes simple usage hints"""
        print('init   - initializes the PKI key management instance with new identity')
        print('renew  - renews publicly trusted certificate for secure web access')
        print('usage  - writes this usage info')

    def do_install(self, line):
        """Alias for init"""
        self.do_init(line)

    def do_init(self, line):
        """
        Initializes the EB client machine, new identity is assigned.
         - New EnigmaBridge identity is fetched
         - EnigmaBridge PKCS#11 Proxy is configured, new token is initialized
         - EJBCA is reinstalled with PKCS#11 support, with new certificates
        Previous configuration data is backed up.
        """
        if not self.check_root() or not self.check_pid():
            return self.return_code(1)

        print('Going to install PKI system and enrol it to the Enigma Bridge FIPS140-2 encryption service.\n')

        config = Core.read_configuration()
        if config is not None and config.has_nonempty_config():
            print('\nWARNING! This is a destructive process!')
            print('WARNING! The previous installation will be overwritten.\n')
            should_continue = self.ask_proceed(support_non_interactive=True)
            if not should_continue:
                return self.return_code(1)

            print('\nWARNING! Configuration already exists in the file %s' % (Core.get_config_file_path()))
            print('The configuration will be overwritten by a new one (current config will be backed up)\n')
            should_continue = self.ask_proceed(support_non_interactive=True)
            if not should_continue:
                return self.return_code(1)

            # Backup the old config
            fname = Core.backup_configuration(config)
            print('Configuration has been backed up: %s\n' % fname)

        # Reinit
        email = self.ask_for_email()
        eb_cfg = Core.get_default_eb_config()

        # Ask user explicitly if he wants to continue with the registration process.
        # Terms & Conditions of the AMIs tells us to ask user whether we can connect to the servers.
        print('')
        print('-'*self.get_term_width())
        print('\nThe installation is about to start.')
        print('During the installation we collect the following ec2 metadata: ')
        print('  - ami-id')
        print('  - instance-id')
        print('  - instance-type')
        print('  - placement')
        print('  - public-ipv4')
        print('  - public-hostname')
        print('')
        print(self.wrap_term(single_string=True, max_width=80,
                             text='The data above together with your e-mail address will be sent '
                                  'to our EnigmaBridge registration server during the installation. Then we generate a '
                                  'dynamic DNS hostname and a new EnigmaBridge user account for you. '
                                  'The EnigmaBridge account is used to generate new RSA keys in the EnigmaBridge secure hardware '
                                  'to boost your PKI security.'))
        print('')
        print(self.wrap_term(single_string=True, max_width=80,
                             text='Moreover we provide you a static DNS host name that will work even after your IP address changes. '
                                  'In order to access PKI administration web interface in a secure way we generate a LetsEncrypt '
                                  'certificate for you on this domain. For this we need to communicate with the LetsEncrypt '
                                  'certificate authority and TCP port 443 open on this host so they can check the domain validity.'))
        print('')
        print(self.wrap_term(single_string=True, max_width=80,
                             text='The privacy policy and more details can be found here: https://enigmabridge.com/amazonpki'))
        print('')
        print(self.wrap_term(single_string=True, max_width=80,
                             text='In order to continue with the installation we need your consent with the network '
                                  'communication the instance will be doing during the installation as outlined in the description above'))

        print('')
        should_continue = self.ask_proceed('Do you agree with the installation process as outlined above? (Y/n): ', support_non_interactive=True)
        if not should_continue:
            return self.return_code(1)

        print('-'*self.get_term_width())
        try:
            reg_svc = Registration(email=email, eb_config=eb_cfg)
            soft_config = SoftHsmV1Config()
            ejbca = Ejbca(print_output=True)
            syscfg = SysConfig(print_output=True)

            # Check if we have EJBCA resources on the drive
            if not ejbca.test_environment():
                print('\nError: Environment is damaged, some assets are missing for the key management installation. Cannot continue.')
                return self.return_code(1)

            # Determine if we have enough RAM for the work.
            # If not, a new swap file is created so the system has at least 2GB total memory space
            # for compilation & deployment.
            if not syscfg.is_enough_ram():
                total_mem = syscfg.get_total_usable_mem()
                print('\nTotal memory in the system is low: %d MB, installation requires at least 2GB'
                      % int(math.ceil(total_mem/1024/1024)))

                print('New swap file will be installed in /var')
                print('It will take approximately 2 minutes...')
                code, swap_name, swap_size = syscfg.create_swap()
                if code == 0:
                    print('\nNew swap file was created %s %d MB and activated' % (swap_name,int(math.ceil(total_mem/1024/1024))))
                else:
                    print('\nSwap file could not be created. Please, inspect the problem and try again')
                    return self.return_code(1)

                # Recheck
                if not syscfg.is_enough_ram():
                    print('Error: still not enough memory. Please, resolve the issue and try again')
                    return self.return_code(1)
                print('')

            # Lets encrypt reachability test
            port_ok = self.le_check_port(critical=False)
            if not port_ok:
                return self.return_code(10)

            # Creates a new RSA key-pair identity
            # Identity relates to bound DNS names and username.
            # Requests for DNS manipulation need to be signed with the private key.
            reg_svc.new_identity(id_dir=CONFIG_DIR, backup_dir=CONFIG_DIR_OLD)

            # New client registration (new username, password, apikey).
            new_config = reg_svc.new_registration()

            # Custom hostname for EJBCA - not yet supported
            new_config.ejbca_hostname_custom = False

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
                        print('\nNew domains registered for this host: ')
                        for domain in new_config.domains:
                            print('  - %s' % domain)
                        print('')

                except Exception as e:
                    domain_ctr += 1
                    if self.args.debug:
                        traceback.print_exc()

                    if self.noninteractive:
                        if domain_ctr >= self.args.attempts:
                            break
                    else:
                        print('\nError during domain registration, no dynamic domain will be assigned')
                        should_continue = self.ask_proceed('Do you want to try again? (Y/n): ')
                        if not should_continue:
                            break

            # Is it OK if domain assignment failed?
            if not domain_is_ok:
                if domain_ignore:
                    print('\nDomain could not be assigned, installation continues. You can try domain reassign later')
                else:
                    print('\nDomain could not be assigned, installation aborted')
                    return self.return_code(1)

            # Install to the OS
            syscfg.install_onboot_check()
            syscfg.install_cron_renew()

            # Dump config & SoftHSM
            conf_file = Core.write_configuration(new_config)
            print('New configuration was written to: %s\n' % conf_file)

            # SoftHSMv1 reconfigure
            soft_config_backup_location = soft_config.backup_current_config_file()
            print('SoftHSMv1 configuration has been backed up to: %s' % soft_config_backup_location)

            soft_config.configure(new_config)
            soft_config_file = soft_config.write_config()

            print('New SoftHSMv1 configuration has been written to: %s\n' % soft_config_file)

            # Init the token
            backup_dir = soft_config.backup_previous_token_dir()
            if backup_dir is not None:
                print('SoftHSMv1 previous token database moved to: %s' % backup_dir)

            out, err = soft_config.init_token(user=ejbca.JBOSS_USER)
            print('SoftHSMv1 initialization: %s' % out)

            # EJBCA configuration
            print('Going to install PKI system')
            print('  This may take 15 minutes or less. Please, do not interrupt the installation')
            print('  and wait until the process completes.\n')

            ejbca.set_config(new_config)
            ejbca.set_domains(new_config.domains)
            ejbca.configure()

            if ejbca.ejbca_install_result != 0:
                print('\nPKI installation error. Please try again.')
                return self.return_code(1)

            Core.write_configuration(ejbca.config)
            print('\nPKI installed successfully.')

            # Generate new keys
            print('\nGoing to generate EnigmaBridge keys in the crypto token:')
            ret, out, err = ejbca.pkcs11_generate_default_key_set(softhsm=soft_config)
            key_gen_cmds = [
                    ejbca.pkcs11_get_generate_key_cmd(softhsm=soft_config, bit_size=2048, alias='signKey', slot_id=0),
                    ejbca.pkcs11_get_generate_key_cmd(softhsm=soft_config, bit_size=2048, alias='defaultKey', slot_id=0),
                    ejbca.pkcs11_get_generate_key_cmd(softhsm=soft_config, bit_size=1024, alias='testKey', slot_id=0)
                ]

            if ret != 0:
                print('\nError generating new keys')
                print('You can do it later manually by calling')

                for tmpcmd in key_gen_cmds:
                    print('  %s' % ejbca.pkcs11_get_command(tmpcmd))

                print('\nError from the command:')
                print(''.join(out))
                print('\n')
                print(''.join(err))
            else:
                print('\nEnigmaBridge tokens generated successfully')
                print('You can use these newly generated keys for your CA or generate another ones with:')
                for tmpcmd in key_gen_cmds:
                    print('  %s' % ejbca.pkcs11_get_command(tmpcmd))

            # Add SoftHSM crypto token to EJBCA
            print('\nAdding an EnigmaBridge crypto token to your PKI instance:')
            ret, out, err = ejbca.ejbca_add_softhsm_token(softhsm=soft_config, name='EnigmaBridgeToken')
            if ret != 0:
                print('\nError in adding EnigmaBridge token to the PKI instance')
                print('You can add it manually in the PKI (EJBCA) admin page later')
                print('Pin for the SoftHSMv1 (EnigmaBridge) token is 0000')
            else:
                print('\nEnigmaBridgeToken added to the PKI instance')

            # LetsEncrypt enrollment
            le_certificate_installed = self.le_install(ejbca)

            print('\n')
            print('-'*self.get_term_width())
            self.cli_sleep(3)

            print(self.t.underline_green('[OK] System installation is completed'))
            if le_certificate_installed == 0:
                if not domain_is_ok:
                    print('  \nThere was a problem in registering new domain names for you system')
                    print('  Please get in touch with support@enigmabridge.com and we will try to resolve the problem')
            else:
                print('  \nTrusted HTTPS certificate was not installed, most likely reason is port 443 being closed by a firewall')
                print('  For more info please check https://enigmabridge.com/support/aws13073')
                print('  We will keep re-trying every 5 minutes.')
                print('\nMeantime, you can access the system at:')
                print('     https://%s:%d/ejbca/adminweb/' % (reg_svc.info_loader.ami_public_hostname, ejbca.PORT))
                print('WARNING: you will have to override web browser security alerts.')

            self.cli_sleep(3)
            print('-'*self.get_term_width())
            print('')
            print(self.t.underline('Please setup your computer for secure connections to your PKI key management system:'))
            time.sleep(0.5)

            # Finalize, P12 file & final instructions
            new_p12 = ejbca.copy_p12_file()
            public_hostname = ejbca.hostname if domain_is_ok else reg_svc.info_loader.ami_public_hostname
            print('\nDownload p12 file: %s' % new_p12)
            print('  scp -i <your_Amazon_PEM_key> ec2-user@%s:%s .' % (public_hostname, new_p12))
            print('  Key import password is: %s' % ejbca.superadmin_pass)
            print('\nThe following page can guide you through p12 import: https://enigmabridge.com/support/aws13076')
            print('Once you import the p12 file to your computer browser/keychain you can connect to the PKI admin interface:')

            if domain_is_ok:
                for domain in new_config.domains:
                    print('  https://%s:%d/ejbca/adminweb/' % (domain, ejbca.PORT))
            else:
                print('  https://%s:%d/ejbca/adminweb/' % (reg_svc.info_loader.ami_public_hostname, ejbca.PORT))

            # Test if EJBCA is reachable on outer interface
            ejbca_open = ejbca.test_port_open(host=reg_svc.info_loader.ami_public_ip)
            if not ejbca_open:
                self.cli_sleep(5)
                print('\nWarning! The PKI port %d is not reachable on the public IP address %s' % (ejbca.PORT, reg_svc.info_loader.ami_public_ip))
                print('If you cannot connect to the PKI kye management interface, consider reconfiguring the AWS Security Groups')
                print('Please get in touch with our support via https://enigmabridge/freshdesk.com')

            self.cli_sleep(5)
            return self.return_code(0)

        except Exception as ex:
            if self.args.debug:
                traceback.print_exc()
            print('Exception in the registration process, cannot continue.')

        return self.return_code(1)

    def do_renew(self, arg):
        """Renews LetsEncrypt certificates used for the JBoss"""
        if not self.check_root() or not self.check_pid():
            return self.return_code(1)

        config = Core.read_configuration()
        if config is None or not config.has_nonempty_config():
            print('\nError! Enigma config file not found %s' % (Core.get_config_file_path()))
            print(' Cannot continue. Have you run init already?\n')
            return self.return_code(1)

        domains = config.domains
        if domains is None or not isinstance(domains, types.ListType) or len(domains) == 0:
            print('\nError! No domains found in the configuration.')
            print(' Cannot continue. Did init complete successfully?')
            return self.return_code(1)

        # If there is no hostname, enrollment probably failed.
        ejbca = Ejbca(print_output=True, jks_pass=config.ejbca_jks_password, config=config)
        ejbca.set_domains(config.ejbca_domains)
        ejbca_host = ejbca.hostname

        le_test = LetsEncrypt()
        enroll_new_cert = ejbca_host is None or len(ejbca_host) == 0 or ejbca_host == 'localhost'
        if enroll_new_cert:
            ejbca.set_domains(domains)
            ejbca_host = ejbca.hostname

        if not enroll_new_cert:
            enroll_new_cert = le_test.is_certificate_ready(domain=ejbca_host) != 0

        # Test LetsEncrypt port
        port_ok = self.le_check_port(critical=True)
        if not port_ok:
            return self.return_code(10)

        ret = 0
        if enroll_new_cert:
            # Enroll a new certificate
            ret = self.le_install(ejbca)
        else:
            # Renew the certs
            ret = self.le_renew(ejbca)
        return self.return_code(ret)

    def do_onboot(self, line):
        """Command called by the init script/systemd on boot, takes care about IP re-registration"""
        if not self.check_root() or not self.check_pid():
            return self.return_code(1)

        config = Core.read_configuration()
        if config is None or not config.has_nonempty_config():
            print('\nError! Enigma config file not found %s' % (Core.get_config_file_path()))
            print(' Cannot continue. Have you run init already?\n')
            return self.return_code(2)

        eb_cfg = Core.get_default_eb_config()
        try:
            reg_svc = Registration(email=config.email, eb_config=eb_cfg, config=config, debug=self.args.debug)
            domains = config.domains
            if domains is not None and isinstance(domains, types.ListType) and len(domains) > 0:
                print('\nDomains currently registered: ')
                for dom in config.domains:
                    print('  - %s' % dom)
                print('')

            if config.ejbca_hostname is not None:
                print('Domain used for your PKI system: %s\n' % config.ejbca_hostname)

            # Identity load (keypair)
            ret = reg_svc.load_identity()
            if ret != 0:
                print('\nError! Could not load identity (key-pair is missing)')
                return self.return_code(3)

            # IP has changed?
            if config.last_ipv4 is not None:
                print('Last IPv4 used for domain registration: %s' % config.last_ipv4)
            print('Current IPv4: %s' % reg_svc.info_loader.ami_public_ip)

            # Assign a new dynamic domain for the host
            domain_is_ok = False
            domain_ctr = 0
            new_config = config
            while not domain_is_ok:
                try:
                    new_config = reg_svc.refresh_domain()

                    if new_config.domains is not None and len(new_config.domains) > 0:
                        domain_is_ok = True
                        print('\nNew domains registered for this host: ')
                        for domain in new_config.domains:
                            print('  - %s' % domain)
                        print('')

                except Exception as e:
                    domain_ctr += 1
                    if self.args.debug:
                        traceback.print_exc()

                    print('\nError during domain registration, no dynamic domain will be assigned')
                    if self.noninteractive:
                        if domain_ctr >= self.args.attempts:
                            break
                    else:
                        should_continue = self.ask_proceed('Do you want to try again? (Y/n): ')
                        if not should_continue:
                            break

            # Is it OK if domain assignment failed?
            if not domain_is_ok:
                print('\nDomain could not be assigned. You can try domain reassign later.')
                return self.return_code(1)

            new_config.last_ipv4 = reg_svc.info_loader.ami_public_ip

            # Is original hostname used in the EJBCA in domains?
            if new_config.ejbca_hostname is not None \
                    and not new_config.ejbca_hostname_custom \
                    and new_config.ejbca_hostname not in new_config.domains:
                print('\nWarning! Returned domains do not correspond to the domain used during EJBCA installation %s' % new_config.ejbca_hostname)
                print('\nThe PKI instance must be redeployed. This operations is not yet supported, please email to support@enigmabridge.com')

            Core.write_configuration(new_config)
            return self.return_code(0)

        except Exception as ex:
            traceback.print_exc()
            print('Exception in the domain registration process, cannot continue.')

        return self.return_code(1)

    def do_change_hostname(self, line):
        """Changes hostname of the EJBCA installation"""
        print('This functionality is not yet implemented')
        print('Basically, its needed:\n'
              ' - edit conf/web.properties and change hostname there\n'
              ' - ant deployear in EJBCA to redeploy EJBCA to JBoss with new settings (preserves DB)\n'
              ' - edit /etc/enigma/config.json ejbca_hostname field\n'
              ' - edit /etc/enigma/config.json ejbca_hostname_custom to true\n'
              ' - call renew command')
        return self.return_code(1)

    def do_undeploy_ejbca(self, line):
        """Undeploys EJBCA without any backup left"""
        if not self.check_root() or not self.check_pid():
            return self.return_code(1)

        print('Going to undeploy and remove EJBCA from the system')
        print('WARNING! This is a destructive process!')
        should_continue = self.ask_proceed(support_non_interactive=True)
        if not should_continue:
            return self.return_code(1)

        print('WARNING! This is the last chance.')
        should_continue = self.ask_proceed(support_non_interactive=True)
        if not should_continue:
            return self.return_code(1)

        ejbca = Ejbca(print_output=True)

        print(' - Undeploying PKI System (EJBCA) from the application server')
        ejbca.undeploy()
        ejbca.jboss_restart()

        print('\nDone.')
        return self.return_code(0)

    def le_check_port(self, ip=None, letsencrypt=None, critical=False):
        if ip is None:
            info = InfoLoader()
            info.load()
            ip = info.ami_public_ip

        if letsencrypt is None:
            letsencrypt = LetsEncrypt()

        print('\nChecking if port %d is open for LetsEncrypt, ip: %s' % (letsencrypt.PORT, ip))
        ok = letsencrypt.test_port_open(ip=ip)
        if ok:
            return True

        print('\nLetsEncrypt port %d is firewalled, please make sure it is reachable on the public interface %s' % (letsencrypt.PORT, ip))
        print('Without port 443 enabled LetsEncrypt cannot verify you own the domain so certificate won\'t be issued.')
        print('Please check AWS Security Groups - Inbound firewall rules for TCP port %d' % (letsencrypt.PORT))

        if self.noninteractive:
            return False

        if critical:
            return False

        else:
            proceed_option = self.PROCEED_YES
            while proceed_option == self.PROCEED_YES:
                proceed_option = self.ask_proceed_quit('Do you want to try again? (Y / n = continue without LetsEncrypt / q=quit): ')
                if proceed_option == self.PROCEED_NO:
                    return True
                elif proceed_option == self.PROCEED_QUIT:
                    return False

                # Test again
                ok = letsencrypt.test_port_open(ip=ip)
                if ok:
                    return True
            pass
        pass

    def le_install(self, ejbca):
        print('\nInstalling LetsEncrypt certificate for: %s' % (', '.join(ejbca.domains)))
        ret = ejbca.le_enroll()
        if ret == 0:
            Core.write_configuration(ejbca.config)
            ejbca.jboss_reload()
            print('\nPublicly trusted certificate installed (issued by LetsEncrypt')

        else:
            print('\nFailed to install publicly trusted certificate, self-signed certificate will be used instead, code=%s.' % ret)
            print('You can try it again later with command renew\n')
        return ret

    def le_renew(self, ejbca):
        le_test = LetsEncrypt()

        renew_needed = self.args.force or le_test.test_certificate_for_renew(domain=ejbca.hostname, renewal_before=60*60*24*20) != 0
        if not renew_needed:
            print('\nRenewal for %s is not needed now. Run with --force to override this' % ejbca.hostname)
            return 0

        print('\nRenewing LetsEncrypt certificate for: %s' % ejbca.hostname)
        ret = ejbca.le_renew()
        if ret == 0:
            Core.write_configuration(ejbca.config)
            ejbca.jboss_reload()
            print('\nNew publicly trusted certificate installed (issued by LetsEncrypt)')

        elif ret == 1:
            print('\nRenewal not needed, certificate did not change')

        else:
            print('\nFailed to renew LetsEncrypt certificate, code=%s.' % ret)
            print('You can try it again later with command renew\n')
        return ret

    def return_code(self, code=0):
        self.last_result = code
        return code

    def cli_sleep(self, iter=5):
        for lines in range(iter):
            print('')
            time.sleep(0.1)

    def ask_proceed_quit(self, question=None, support_non_interactive=False, non_interactive_return=PROCEED_YES, quit_enabled=True):
        """Ask if user wants to proceed"""
        opts = 'Y/n/q' if quit_enabled else 'Y/n'
        question = question if question is not None else ('Do you really want to proceed? (%s): ' % opts)

        if self.noninteractive and not support_non_interactive:
            raise errors.Error('Non-interactive mode not supported for this prompt')

        if self.noninteractive and support_non_interactive:
            if self.args.yes:
                print(question)
                if non_interactive_return == self.PROCEED_YES:
                    print('Y')
                elif non_interactive_return == self.PROCEED_NO:
                    print('n')
                elif non_interactive_return == self.PROCEED_QUIT:
                    print('q')
                else:
                    raise ValueError('Unknown default value')

                return non_interactive_return
            else:
                raise errors.Error('Non-interactive mode for a prompt without --yes flag')

        # Classic interactive prompt
        confirmation = None
        while confirmation != 'y' and confirmation != 'n' and confirmation != 'q':
            confirmation = raw_input(question).strip().lower()
        if confirmation == 'y':
            return self.PROCEED_YES
        elif confirmation == 'n':
            return self.PROCEED_NO
        else:
            return self.PROCEED_QUIT

    def ask_proceed(self, question=None, support_non_interactive=False, non_interactive_return=True):
        """Ask if user wants to proceed"""
        ret = self.ask_proceed_quit(question=question,
                                    support_non_interactive=support_non_interactive,
                                    non_interactive_return=self.PROCEED_YES if non_interactive_return else self.PROCEED_NO,
                                    quit_enabled=False)

        return ret == self.PROCEED_YES

    def ask_for_email(self):
        """Asks user for an email address"""
        confirmation = False
        var = None

        # Take email from the command line
        if self.args.email is not None:
            self.args.email = self.args.email.strip()
            print('Using email passed as an argument: %s' % self.args.email)
            if len(self.args.email) > 0 and not util.safe_email(self.args.email):
                print('Email you have entered is invalid, cannot continue')
                raise ValueError('Invalid email address')
            else:
                return self.args.email

        # Noninteractive mode - use empty email address if got here
        if self.noninteractive:
            return ''

        print('We need your email address for:\n'
              '   a) identity verification in case of a recovery / support \n'
              '   b) LetsEncrypt certificate registration')
        print('It\'s optional but we highly recommend to enter a valid e-mail address (especially on a production system)\n')

        # Asking for email - interactive
        while not confirmation:
            var = raw_input('Please enter your email address [empty]: ').strip()
            question = None
            if len(var) == 0:
                question = 'You have entered an empty email address, is it correct? (Y/n):'
            elif not util.safe_email(var):
                print('Email you have entered is invalid, try again')
                continue
            else:
                question = 'Is this email correct? \'%s\' (Y/n):' % var
            confirmation = self.ask_proceed(question)
        return var

    def check_root(self):
        """Checks if the script was started with root - we need that for file ops :/"""
        uid = os.getuid()
        euid = os.geteuid()
        if uid != 0 and euid != 0:
            print('Error: This action requires root privileges')
            print('Please, start the client with: sudo -E -H ebaws')
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
                    print('\nPID lock acquired')
                return True

            except pid.PidFileAlreadyRunningError as e:
                return True

            except pid.PidFileError as e:
                pidnum = self.core.pidlock_get_pid()
                print('\nError: CLI already running in exclusive mode by PID: %d' % pidnum)

                if self.args.pidlock >= 0 and attempt_ctr > self.args.pidlock:
                    return False

                print('Next check will be performed in few seconds. Waiting...')
                time.sleep(3)
        pass

    def get_term_width(self):
        try:
            width = self.t.width
            if width is None or width <= 0:
                return 80

            return width
        except:
            pass
        return 80

    def wrap_term(self, text="", single_string=False, max_width=None):
        width = self.get_term_width()
        if max_width is not None and width > max_width:
            width = max_width

        res = textwrap.wrap(text, width)
        return res if not single_string else '\n'.join(res)

    def app_main(self):
        # Backup original arguments for later parsing
        args_src = sys.argv

        # Parse our argument list
        parser = argparse.ArgumentParser(description='EnigmaBridge AWS client')
        parser.add_argument('-n', '--non-interactive', dest='noninteractive', action='store_const', const=True,
                            help='non-interactive mode of operation, command line only')
        parser.add_argument('-r', '--attempts', dest='attempts', type=int, default=3,
                            help='number of attempts in non-interactive mode')
        parser.add_argument('-l','--pid-lock', dest='pidlock', type=int, default=-1,
                            help='number of attempts for pidlock acquire')
        parser.add_argument('--debug', dest='debug', action='store_const', const=True,
                            help='enables debug mode')
        parser.add_argument('--verbose', dest='verbose', action='store_const', const=True,
                            help='enables verbose mode')
        parser.add_argument('--force', dest='force', action='store_const', const=True, default=False,
                            help='forces some action (e.g., certificate renewal)')
        parser.add_argument('--email', dest='email', default=None,
                            help='email address to use instead of prompting for one')

        parser.add_argument('--yes', dest='yes', action='store_const', const=True,
                            help='answers yes to the questions in the non-interactive mode, mainly for init')

        parser.add_argument('--allow-update', action='store_const', const=True,
                            help='Inherited option from auto-update wrapper, no action here')
        parser.add_argument('--no-self-upgrade', action='store_const', const=True,
                            help='Inherited option from auto-update wrapper, no action here')
        parser.add_argument('--os-packages-only', action='store_const', const=True,
                            help='Inherited option from auto-update wrapper, no action here')

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

        # Noninteractive - return the last result from the operation (for scripts)
        if self.noninteractive:
            sys.exit(self.last_result)


def main():
    app = App()
    app.app_main()


if __name__ == '__main__':
    main()
