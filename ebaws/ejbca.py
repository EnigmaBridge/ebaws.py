import os
import util
from sarge import run, Capture, Feeder
from ebclient.eb_utils import EBUtils
from datetime import datetime
import time
import sys
import subprocess

__author__ = 'dusanklinec'


class Ejbca(object):
    """
    EJBCA configuration & builder
    """

    # Default home dirs
    EJBCA_HOME = '/home/ec2-user/ejbca_ce_6_3_1_1'
    JBOSS_HOME = '/opt/jboss-as-7.1.1.Final'
    INSTALL_PROPERTIES_FILE = 'conf/install.properties'
    WEB_PROPERTIES_FILE = 'conf/web.properties'
    P12_FILE = 'p12/superadmin.p12'
    PASSWORDS_FILE = '/root/ejbca.passwords'

    # Default installation settings
    INSTALL_PROPERTIES = {
        'ca.name': 'ManagementCA',
        'ca.dn': 'CN=ManagementCA,O=EJBCA EnigmaBridge,C=GB',
        'ca.tokentype': 'soft',
        'ca.keytype': 'RSA',
        'ca.keyspec': '2048',
        'ca.signaturealgorithm': 'SHA256WithRSA',
        'ca.validity': '3650',
        'ca.policy': 'null'
    }

    WEB_PROPERTIES = {
        'cryptotoken.p11.lib.255.name': 'SoftHSMv1',
        'cryptotoken.p11.lib.255.file': '/usr/lib64/softhsm/libsofthsm.so',

        'httpsserver.hostname': 'localhost',
        'httpsserver.dn': 'CN=localhost,O=EJBCA EnigmaBridge,C=GB',

        'superadmin.cn': 'SuperAdmin',
        'superadmin.dn': 'CN=SuperAdmin',
        'superadmin.batch': 'true',

        # Credentials, generated at random, stored into password file
        #'httpsserver.password': 'serverpwd',
        #'java.trustpassword': 'changeit',
        #'superadmin.password': 'ejbca',
    }

    def __init__(self, install_props=None, web_props=None, *args, **kwargs):
        self.install_props = install_props if install_props is not None else {}
        self.web_props = web_props if web_props is not None else {}

        self.http_pass = util.random_password(12)
        self.java_pass = util.random_password(12)
        self.superadmin_pass = util.random_password(12)

        self.ejbca_install_result = 1
        pass

    def get_ejbca_home(self):
        """
        Returns EJBCA home, first try to look at env var, then return default val
        :return:
        """
        if 'EJBCA_HOME' in os.environ and len(os.environ['EJBCA_HOME']) > 0:
            return os.path.abspath(os.environ['EJBCA_HOME'])
        else:
            return os.path.abspath(self.EJBCA_HOME)

    def get_jboss_home(self):
        """
        Returns JBoss home directory, first try to look at env var, then return default val
        :return:
        """
        if 'JBOSS_HOME' in os.environ and len(os.environ['JBOSS_HOME']) > 0:
            return os.path.abspath(os.environ['JBOSS_HOME'])
        else:
            return os.path.abspath(self.JBOSS_HOME)

    def get_install_prop_file(self):
        return os.path.abspath(os.path.join(self.get_ejbca_home(), self.INSTALL_PROPERTIES_FILE))

    def get_web_prop_file(self):
        return os.path.abspath(os.path.join(self.get_ejbca_home(), self.WEB_PROPERTIES_FILE))

    def properties_to_string(self, prop):
        """
        Converts dict based properties to a string
        :return:
        """
        result = []
        for k in prop:
            result.append("%s=%s" % (k, prop[k]))
        result = sorted(result)
        return '\n'.join(result)

    def update_properties(self):
        """
        Updates properties files of the ejbca
        :return:
        """
        file_web = self.get_web_prop_file()
        file_ins = self.get_install_prop_file()

        prop_web = EBUtils.merge(self.WEB_PROPERTIES, self.web_props)
        prop_ins = EBUtils.merge(self.INSTALL_PROPERTIES, self.install_props)

        prop_hdr = '#\n'
        prop_hdr += '# Config file generated: %s\n' % (datetime.now().strftime("%Y-%m-%d %H:%M"))
        prop_hdr += '#\n'

        file_web_hnd = None
        file_ins_hnd = None
        try:
            file_web_hnd, file_web_backup = util.safe_create_with_backup(file_web, 'w', 0o644)
            file_ins_hnd, file_ins_backup = util.safe_create_with_backup(file_ins, 'w', 0o644)

            file_web_hnd.write(prop_hdr + self.properties_to_string(prop_web)+"\n\n")
            file_ins_hnd.write(prop_hdr + self.properties_to_string(prop_ins)+"\n\n")
        finally:
            if file_web_hnd is not None:
                file_web_hnd.close()
            if file_ins_hnd is not None:
                file_ins_hnd.close()

    def ant_deploy(self):
        """
        Runs ant_deploy task
        Should not be needed, is performed only once
        :return:
        """
        feeder = Feeder()
        cwd = self.get_ejbca_home()

        p = run('ant deploy',
                input=feeder, async=True,
                stdout=Capture(buffer_size=1),
                stderr=Capture(buffer_size=1),
                cwd=cwd)

        out_acc = []
        err_acc = []
        ret_code = 1

        while len(p.commands) == 0:
            time.sleep(0.15)

        try:
            while p.commands[0].returncode is None:
                out = p.stdout.readline()
                err = p.stderr.readline()

                # If output - react on input challenges
                if out is not None and len(out) > 0:
                    out_acc.append(out)
                    if out.startswith('Please enter'):            # default - use default value, no starving
                        feeder.feed('\n')
                    elif out.startswith('[input] Please enter'):  # default - use default value, no starving
                        feeder.feed('\n')

                # Collect error
                if err is not None and len(err)>0:
                    err_acc.append(err)
                    sys.stderr.write('stderr: ' + err + "\n")

                p.commands[0].poll()
                time.sleep(0.01)

            ret_code = p.commands[0].returncode

            # Collect output to accumulator
            rest_out = p.stdout.readlines()
            if rest_out is not None and len(rest_out) > 0:
                for i in rest_out: out_acc.append(i)

            # Collect error to accumulator
            rest_err = p.stderr.readlines()
            if rest_err is not None and len(rest_err) > 0:
                for i in rest_err: err_acc.append(i)
                sys.stderr.write('stderr: ' + '\n'.join(p.stderr.readlines()) + '\n')

            if ret_code != 0:
                sys.stderr.write('Error, process returned with invalid result code: %s\n' % p.commands[0].returncode)

            return ret_code, out_acc, err_acc

        finally:
            feeder.close()
        pass

    def ant_install(self):
        """
        install a new EJBCA instance.
        Note the database must be removed before running this. Install target can
        be called only once.
        :return:
        """
        feeder = Feeder()
        cwd = self.get_ejbca_home()

        p = run('ant install',
                input=feeder, async=True,
                stdout=Capture(buffer_size=1),
                stderr=Capture(buffer_size=1),
                cwd=cwd)

        ret_code = 1

        while len(p.commands) == 0:
            time.sleep(0.15)

        log_file = '/tmp/ant-install.log'
        util.delete_file_backup(log_file)
        log = util.safe_open(log_file, mode='w', chmod=0o600)

        try:
            while p.commands[0].returncode is None:
                out = p.stdout.readline()
                err = p.stderr.readline()

                if out is not None and len(out) > 0:
                    log.write(out)
                    log.flush()
                    sys.stderr.write('.')
                    if 'truststore with the CA certificate for https' in out:
                        feeder.feed(self.java_pass + '\n')
                    elif 'keystore with the TLS key for https' in out:
                        feeder.feed(self.http_pass + '\n')
                    elif 'the superadmin password' in out:
                        feeder.feed(self.superadmin_pass + '\n')
                    elif 'password CA token password':
                        feeder.feed('\n')
                    elif out.startswith('Please enter'):          # default - use default value, no starving
                        feeder.feed('\n')
                    elif out.startswith('[input] Please enter'):  # default - use default value, no starving
                        feeder.feed('\n')

                if err is not None and len(err)>0:
                    log.write(err)
                    log.flush()
                    sys.stderr.write('.')

                p.commands[0].poll()
                time.sleep(0.01)

            ret_code = p.commands[0].returncode

            rest_out = p.stdout.readlines()
            if rest_out is not None and len(rest_out) > 0:
                for i in rest_out:
                    log.write(i)
                    sys.stderr.write('.')
                log.flush()

            rest_err = p.stderr.readlines()
            if rest_err is not None and len(rest_err) > 0:
                for i in rest_err:
                    log.write(i)
                log.flush()

            sys.stderr.write('\n')
            if ret_code != 0:
                sys.stderr.write('Error, process returned with invalid result code: %s\n' % p.commands[0].returncode)
                sys.stderr.write('For more details please refer to %s \n' % log_file)

        finally:
            feeder.close()
            log.close()
            pass

        return ret_code

    def jboss_stop(self):
        """
        Stops Jboss server, blocking
        :return:
        """
        p = subprocess.Popen(['/etc/init.d/jboss', 'stop'])
        p.communicate()
        return p.wait()
        # if done with sarge - jboss is terminated when python is terminated...
        # p = run('/etc/init.d/jboss stop')
        # return p.commands[0].returncode

    def jboss_start(self):
        """
        Starts jboss server, blocking
        :return:
        """
        p = subprocess.Popen(['/etc/init.d/jboss', 'start'])
        p.communicate()
        return p.wait()
        # if done with sarge - jboss is terminated when python is terminated...
        # p = run('/etc/init.d/jboss start')
        # return p.commands[0].returncode

    def jboss_backup_database(self):
        """
        Removes original database, moving it to a backup location.
        :return:
        """
        jboss_dir = self.get_jboss_home()
        db1 = os.path.join(jboss_dir, 'ejbcadb.h2.db')
        db2 = os.path.join(jboss_dir, 'ejbcadb.trace.db')

        backup1 = util.delete_file_backup(db1)
        backup2 = util.delete_file_backup(db2)
        return backup1, backup2

    def backup_passwords(self):
        """
        Backups the generated passwords to /root/ejbca.passwords
        :return:
        """
        util.delete_file_backup(self.PASSWORDS_FILE, chmod=0o600)
        with util.safe_open(self.PASSWORDS_FILE, chmod=0o600) as f:
            f.write('httpsserver.password=%s\n' % self.http_pass)
            f.write('java.trustpassword=%s\n' % self.java_pass)
            f.write('superadmin.password=%s\n' % self.superadmin_pass)
            f.flush()

    def get_p12_file(self):
        return os.path.abspath(os.path.join(self.get_ejbca_home(), self.P12_FILE))

    def configure(self):
        """
        Configures EJBCA for installation deployment
        :return:
        """

        # 1. update properties file
        self.update_properties()
        self.backup_passwords()

        # 2. and install
        self.jboss_stop()
        self.jboss_backup_database()
        self.jboss_start()

        self.ejbca_install_result = self.ant_install()
        pass




