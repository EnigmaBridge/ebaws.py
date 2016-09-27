import os
import util
from sarge import run, Capture, Feeder
from ebclient.eb_utils import EBUtils
from datetime import datetime
import time
import sys
import types
import subprocess

__author__ = 'dusanklinec'


class Ejbca(object):
    """
    EJBCA configuration & builder
    """

    # Default home dirs
    EJBCA_HOME = '/opt/ejbca_ce_6_3_1_1'
    JBOSS_HOME = '/opt/jboss-eap-6.4.0'

    INSTALL_PROPERTIES_FILE = 'conf/install.properties'
    WEB_PROPERTIES_FILE = 'conf/web.properties'
    P12_FILE = 'p12/superadmin.p12'

    PASSWORDS_FILE = '/root/ejbca.passwords'
    DB_BACKUPS = '/root/ejbcadb'

    JBOSS_CLI = 'bin/jboss-cli.sh'

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

    def __init__(self, install_props=None, web_props=None, print_output=False, *args, **kwargs):
        self.install_props = install_props if install_props is not None else {}
        self.web_props = web_props if web_props is not None else {}

        self.http_pass = util.random_password(16)
        self.java_pass = util.random_password(16)
        self.superadmin_pass = util.random_password(16)

        self.print_output = print_output

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

    def cli_cmd(self, cmd, log_obj=None, write_dots=False, on_out=None, on_err=None, ant_answer=True, cwd=None):
        """
        Runs command line task
        Used for ant and jboss-cli.sh
        :return:
        """
        feeder = Feeder()
        default_cwd = self.get_ejbca_home()
        p = run(cmd,
                input=feeder, async=True,
                stdout=Capture(buffer_size=1),
                stderr=Capture(buffer_size=1),
                cwd=cwd if cwd is not None else default_cwd)

        out_acc = []
        err_acc = []
        ret_code = 1
        log = None
        close_log = False

        # Logging - either filename or logger itself
        if log_obj is not None:
            if isinstance(log_obj, types.StringTypes):
                util.delete_file_backup(log_obj)
                log = util.safe_open(log_obj, mode='w', chmod=0o600)
                close_log = True
            else:
                log = log_obj

        try:
            while len(p.commands) == 0:
                time.sleep(0.15)

            while p.commands[0].returncode is None:
                out = p.stdout.readline()
                err = p.stderr.readline()

                # If output - react on input challenges
                if out is not None and len(out) > 0:
                    out_acc.append(out)

                    if log is not None:
                        log.write(out)
                        log.flush()

                    if write_dots:
                        sys.stderr.write('.')

                    if on_out is not None:
                        on_out(out, feeder)
                    elif ant_answer:
                        if out.strip().startswith('Please enter'):            # default - use default value, no starving
                            feeder.feed('\n')
                        elif out.strip().startswith('[input] Please enter'):  # default - use default value, no starving
                            feeder.feed('\n')

                # Collect error
                if err is not None and len(err)>0:
                    err_acc.append(err)

                    if log is not None:
                        log.write(err)
                        log.flush()

                    if write_dots:
                        sys.stderr.write('.')

                    if on_err is not None:
                        on_err(err, feeder)

                p.commands[0].poll()
                time.sleep(0.01)

            ret_code = p.commands[0].returncode

            # Collect output to accumulator
            rest_out = p.stdout.readlines()
            if rest_out is not None and len(rest_out) > 0:
                for out in rest_out:
                    out_acc.append(out)
                    if log is not None:
                        log.write(out)
                        log.flush()
                    if on_out is not None:
                        on_out(out, feeder)

            # Collect error to accumulator
            rest_err = p.stderr.readlines()
            if rest_err is not None and len(rest_err) > 0:
                for err in rest_err:
                    err_acc.append(err)
                    if log is not None:
                        log.write(err)
                        log.flush()
                    if on_err is not None:
                        on_err(err, feeder)

            return ret_code, out_acc, err_acc

        finally:
            feeder.close()
            if close_log:
                log.close()
        pass

    def ant_cmd(self, cmd, log_obj=None, write_dots=False, on_out=None, on_err=None):
        ret, out, err = self.cli_cmd('sudo -E -H -u jboss ant ' + cmd, log_obj=log_obj, write_dots=write_dots, on_out=on_out, on_err=on_err, ant_answer=True)
        if ret != 0:
            sys.stderr.write('\nError, process returned with invalid result code: %s\n' % ret)
            if isinstance(log_obj, types.StringTypes):
                sys.stderr.write('For more details please refer to %s \n' % log_obj)
        if write_dots:
            sys.stderr.write('\n')
        return ret, out, err

    def ant_deploy(self):
        return self.ant_cmd('deploy', log_obj='/tmp/ant-deploy.log', write_dots=self.print_output)

    def ant_deployear(self):
        return self.ant_cmd('deployear', log_obj='/tmp/ant-deployear.log', write_dots=self.print_output)

    def ant_install_answer(self, out, feeder):
        out = out.strip()
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

    def ant_install(self):
        """
        Installation
        :return:
        """
        return self.ant_cmd('install', log_obj='/tmp/ant-install.log', write_dots=self.print_output, on_out=self.ant_install_answer)

    def jboss_cmd(self, cmd):
        cli = os.path.abspath(os.path.join(self.get_jboss_home(), self.JBOSS_CLI))
        cli_cmd = cli + (" -c '%s'" % cmd)

        with open('/tmp/jboss-cli.log', 'a+') as logger:
            ret, out, err = self.cli_cmd(cli_cmd, log_obj=logger, write_dots=self.print_output, ant_answer=False)
            return ret, out, err

    def jboss_reload(self):
        return self.jboss_cmd(':reload')

    def jboss_undeploy(self):
        return self.jboss_cmd('undeploy ejbca.ear')

    def jboss_remove_datasource(self):
        return self.jboss_cmd('data-source remove --name=ejbcads')

    def jboss_rollback_ejbca(self):
        cmds = ['/core-service=management/security-realm=SSLRealm/authentication=truststore:remove',
                '/core-service=management/security-realm=SSLRealm/server-identity=ssl:remove',
                '/core-service=management/security-realm=SSLRealm:remove',
                '/socket-binding-group=standard-sockets/socket-binding=httpspub:remove',
                '/subsystem=undertow/server=default-server/https-listener=httpspub:remove',
                '/socket-binding-group=standard-sockets/socket-binding=httpspriv:remove',
                '/subsystem=undertow/server=default-server/https-listener=httpspriv:remove',
                '/socket-binding-group=standard-sockets/socket-binding=http:remove',
                '/subsystem=undertow/server=default-server/http-listener=http:remove',
                '/subsystem=undertow/server=default-server/http-listener=default:remove',
                ':reload',

                '/system-property=org.apache.catalina.connector.URI_ENCODING:remove',
                '/system-property=org.apache.catalina.connector.USE_BODY_ENCODING_FOR_QUERY_STRING:remove',

                '/interface=http:remove',
                '/interface=httpspub:remove',
                '/interface=httpspriv:remove']
        for cmd in cmds:
            self.jboss_cmd(cmd)
        self.jboss_reload()

    def jboss_backup_database(self):
        """
        Removes original database, moving it to a backup location.
        :return:
        """
        jboss_dir = self.get_jboss_home()
        db1 = os.path.join(jboss_dir, 'ejbcadb.h2.db')
        db2 = os.path.join(jboss_dir, 'ejbcadb.trace.db')
        db3 = os.path.join(jboss_dir, 'ejbcadb.lock.db')

        util.make_or_verify_dir(self.DB_BACKUPS)

        backup1 = util.delete_file_backup(db1, backup_dir=self.DB_BACKUPS)
        backup2 = util.delete_file_backup(db2, backup_dir=self.DB_BACKUPS)
        backup3 = util.delete_file_backup(db3, backup_dir=self.DB_BACKUPS)
        return backup1, backup2, backup3

    def jboss_fix_privileges(self):
        p = subprocess.Popen('sudo chown -R jboss:jboss ' + self.get_jboss_home(), shell=True)
        p.wait()
        p = subprocess.Popen('sudo chown -R jboss:jboss ' + self.get_ejbca_home(), shell=True)
        p.wait()

    def jboss_restart(self):
        os.spawnlp(os.P_NOWAIT, "sudo", "bash", "bash", "-c",
                   "setsid /etc/init.d/jboss-eap-6.4.0 restart 2>/dev/null >/dev/null </dev/null &")
        time.sleep(20)

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
        if self.print_output:
            print " - Updating settings"
        self.update_properties()
        self.backup_passwords()

        # 2. Undeploy original EJBCA
        if self.print_output:
            print " - Cleaning JBoss environment (DB backup)"
        self.jboss_undeploy()
        self.jboss_remove_datasource()
        self.jboss_rollback_ejbca()
        self.jboss_reload()

        # restart jboss
        if self.print_output:
            print "\n - Restarting JBoss, please wait..."
        self.jboss_restart()
        self.jboss_backup_database()
        self.jboss_fix_privileges()
        self.jboss_reload()

        # 3. deploy
        if self.print_output:
            print "\n - Deploying EJBCA"
        res, out, err = self.ant_deploy()
        self.ejbca_install_result = res
        if res != 0:
            return 2

        # 4. install
        if self.print_output:
            print " - Installing EJBCA"
        self.jboss_fix_privileges()
        res, out, err = self.ant_install()
        self.ejbca_install_result = res
        self.jboss_fix_privileges()
        return res





