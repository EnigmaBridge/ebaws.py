import os
import util
from sarge import run, Capture, Feeder
from ebclient.eb_utils import EBUtils
from datetime import datetime

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

    # Default installation settings
    INSTALL_PROPERTIES = {
        'ca.name': 'ManagementCA',
        'ca.dn': 'CN=ManagementCA,O=EJBCA EnigmaBridge,C=GB',
        'ca.tokentype': 'soft',
        'ca.keytype': 'RSA',
        'ca.keyspec': '2048',
        'ca.signaturealgorithm': 'SHA256WithRSA',
        'ca.validity': '3650',
        'ca.policy': 'null',
        'ca.tokenproperties': '${ca.tokenproperties}'
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
        'httpsserver.password': 'serverpwd',
        'java.trustpassword': 'changeit',
        'superadmin.password': 'ejbca',
    }

    def __init__(self, install_props=None, web_props=None, *args, **kwargs):
        self.install_props = install_props if install_props is not None else {}
        self.web_props = web_props if web_props is not None else {}
        pass

    def get_ejbca_home(self):
        """
        Returns EJBCA home, first try to look at env var, then return default val
        :return:
        """
        if 'EJBCA_HOME' in os.environ and len(os.environ['EJBCA_HOME']) > 0:
            return os.environ['EJBCA_HOME']
        else:
            return self.EJBCA_HOME

    def get_jboss_home(self):
        """
        Returns JBoss home directory, first try to look at env var, then return default val
        :return:
        """
        if 'JBOSS_HOME' in os.environ and len(os.environ['JBOSS_HOME']) > 0:
            return os.environ['JBOSS_HOME']
        else:
            return self.JBOSS_HOME

    def get_install_prop_file(self):
        return os.path.join(self.get_ejbca_home(), self.INSTALL_PROPERTIES_FILE)

    def get_web_prop_file(self):
        return os.path.join(self.get_ejbca_home(), self.WEB_PROPERTIES_FILE)

    def properties_to_string(self, prop):
        """
        Converts dict based properties to a string
        :return:
        """
        result = []
        for k in prop:
            result.append("%s=%s" % (k, prop[k]))
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

        prop_hdr = '''
            #
            # Config file generated: %s
            #
        ''' % (datetime.now().strftime("%Y-%m-%d %H:%M"))

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

    def configure(self):
        """
        Configures EJBCA for installation deployment
        :return:
        """

        # 1. update properties file
        self.update_properties()

        # 2. and install

        pass




