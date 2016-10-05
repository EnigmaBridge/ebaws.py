import os
import util
from sarge import run, Capture, Feeder
from ebclient.eb_utils import EBUtils
from datetime import datetime
import time
import sys
import types
import errors
import subprocess
import shutil
import re


__author__ = 'dusanklinec'


class LetsEncryptToJks(object):
    """
    Imports Lets encrypt certificate to Java Key Store (JKS)
    """
    PRIVATE_KEY = 'privkey.pem'
    CERT = 'cert.pem'
    CA = 'fullchain.pem'
    TMP_P12 = '/tmp/tmpcert.p12'
    OPENSSL_LOG = '/tmp/openssl.log'
    KEYTOOL_LOG = '/tmp/keytool.log'

    def __init__(self, cert_dir=None, jks_path=None, jks_alias='tomcat', password='password', keytool_path=None, print_output=False, *args, **kwargs):
        self.cert_dir = cert_dir
        self.jks_path = jks_path
        self.jks_alias = jks_alias
        self.password = password
        self.keytool_path = keytool_path
        self.print_output = print_output

    def get_keytool(self):
        return 'keytool' if self.keytool_path is None else self.keytool_path

    def print_error(self, msg):
        if self.print_output:
            sys.stderr.write(msg)

    def del_entry(self, alias=None, password=None, keystore=None):
        """
        keytool -delete -alias mydomain -keystore keystore.jks
        """
        keytool = self.get_keytool()
        if not util.exe_exists(keytool):
            self.print_error('Error, keytool command not found')
            return 4

        alias = alias if alias is not None else self.jks_alias
        password = password if password is not None else self.password
        keystore = keystore if keystore is not None else self.jks_path

        cmd = 'sudo -E -H %s -delete -alias "%s" -keystore "%s" -srcstorepass "%s"' \
              % (keytool, alias, keystore, password)

        log_obj = self.KEYTOOL_LOG
        ret, out, err = util.cli_cmd_sync(cmd, log_obj=log_obj, write_dots=self.print_output)
        if ret != 0:
            self.print_error('\nKeyTool command failed.')
            self.print_error('For more information please refer to the log file: %s' % log_obj)
            return 6
        return 0

    def convert(self):
        priv_file = os.path.join(self.cert_dir, self.PRIVATE_KEY)
        cert_file = os.path.join(self.cert_dir, self.CERT)
        ca_file = os.path.join(self.cert_dir, self.CA)

        if not os.path.exists(priv_file):
            self.print_error('Error, private key not found at %s\n' % priv_file)
            return 1

        if not os.path.exists(cert_file):
            self.print_error('Error, cert not found at %s\n' % cert_file)
            return 2

        if not os.path.exists(ca_file):
            self.print_error('Error, fullchain file not found at %s\n' % ca_file)
            return 3

        keytool = self.get_keytool()
        if not util.exe_exists(keytool):
            self.print_error('Error, keytool command not found')
            return 4

        openssl = 'openssl'
        if not util.exe_exists(openssl):
            self.print_error('Error, openssl command not found')
            return 5

        # 1. step - create p12 file
        p12_file, p12_name = util.unique_file(self.TMP_P12, mode=0o600)
        p12_file.close()

        try:
            cmd = 'sudo -E -H %s pkcs12 -export -out "%s" ' \
                  ' -password pass:"%s" ' \
                  ' -inkey "%s" ' \
                  ' -in "%s" ' \
                  ' -certfile "%s" ' \
                  ' -name "%s" ' % (openssl, p12_name, self.password, priv_file, cert_file, ca_file, self.jks_alias)

            log_obj = self.OPENSSL_LOG
            ret, out, err = util.cli_cmd_sync(cmd, log_obj=log_obj, write_dots=self.print_output)
            if ret != 0:
                self.print_error('\nOpenSSL command failed.')
                self.print_error('For more information please refer to the log file: %s' % log_obj)
                return 6

            # 2. step - create JKS
            cmd = 'sudo -E -H %s -importkeystore -deststorepass "%s" ' \
                  ' -destkeypass "%s" ' \
                  ' -destkeystore "%s" ' \
                  ' -srckeystore "%s" ' \
                  ' -srcstoretype PKCS12 ' \
                  ' -srcstorepass "%s" ' \
                  ' -alias "%s" ' % (keytool, self.password, self.password, self.jks_path, p12_name, self.password, self.jks_alias)

            log_obj = self.KEYTOOL_LOG
            ret, out, err = util.cli_cmd_sync(cmd, log_obj=log_obj, write_dots=self.print_output)
            if ret != 0:
                self.print_error('\nKeytool command failed.')
                self.print_error('For more information please refer to the log file: %s' % log_obj)
                return 7

            return 0

        finally:
            if os.path.exists(p12_name):
                    os.remove(p12_name)


class LetsEncrypt(object):
    """
    LetsEncrypt integration
    """

    CERTBOT_PATH = '/usr/local/bin/certbot'
    LE_CERT_PATH = '/etc/letsencrypt/live'
    CERTBOT_LOG = '/tmp/certbot.log'

    def __init__(self, email=None, domains=None, print_output=False, *args, **kwargs):
        self.email = email
        self.domains = domains
        self.print_output = print_output

    def certonly(self, email=None, domains=None, expand=False):
        if email is not None:
            self.email = email
        if domains is not None:
            self.domains = domains

        cmd = self.get_standalone_cmd(self.domains, email=self.email, expand=expand)
        cmd_exec = 'sudo -E -H %s %s' % (self.CERTBOT_PATH, cmd)
        log_obj = self.CERTBOT_LOG

        ret, out, err = util.cli_cmd_sync(cmd_exec, log_obj=log_obj, write_dots=self.print_output)
        if ret != 0:
            self.print_error('\nCertbot command failed: %s\n' % cmd_exec)
            self.print_error('For more information please refer to the log file: %s' % log_obj)

        return ret, out, err

    def renew(self):
        cmd = self.get_renew_cmd()
        cmd_exec = 'sudo -E -H %s %s' % (self.CERTBOT_PATH, cmd)
        log_obj = self.CERTBOT_LOG

        ret, out, err = util.cli_cmd_sync(cmd_exec, log_obj=log_obj, write_dots=self.print_output)
        if ret != 0 and self.print_output:
            self.print_error('\nCertbot command failed: %s\n' % cmd_exec)
            self.print_error('For more information please refer to the log file: %s' % log_obj)

        return ret, out, err

    def get_certificate_dir(self, domain=None):
        if domain is None:
            return self.LE_CERT_PATH
        else:
            return os.path.join(self.LE_CERT_PATH, domain)

    def print_error(self, msg):
        if self.print_output:
            sys.stderr.write(msg)

    @staticmethod
    def get_standalone_cmd(domain, email=None, expand=False):
        cmd_email_part = LetsEncrypt.get_email_cmd(email)

        domains = domain if isinstance(domain, types.ListType) else [domain]
        domains = ['"%s"' % x.strip() for x in domains]
        cmd_domains_part = ' -d ' + (' -d '.join(domains))

        cmd_expand_part = '' if not expand else ' --expand '

        cmd = 'certonly --standalone --text -n --agree-tos %s %s %s' % (cmd_email_part, cmd_domains_part, cmd_expand_part)
        return cmd

    @staticmethod
    def get_renew_cmd():
        return 'renew -n'

    @staticmethod
    def get_email_cmd(email):
        email = email if email is not None else ''
        email = email.strip()

        cmd = '--register-unsafely-without-email'
        if len(email) > 0:
            cmd = '--email ' + email
        return cmd
