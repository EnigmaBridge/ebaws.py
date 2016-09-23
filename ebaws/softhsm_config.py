import os
import json
from core import Core
import util
from consts import *
from errors import *
from config import Config
from datetime import datetime

__author__ = 'dusanklinec'


class SoftHsmV1Config(object):
    """
    Class for configuring SoftHSMv1 instance for EB
    """
    CONFIG_FILE = '/etc/softhsm.conf'
    DEFAULT_SLOT_CONFIG = {
            'slot': 0,
            'db': '/var/lib/softhsm/slot0.db',
            "host": "site2.enigmabridge.com",
            "port": 11110,
            "enrollPort": 11112,
            "apikey": "TEST_API",
            "genRSA": True,

            "retry": {
                "maxRetry": 4,
                "jitterBase": 250,
                "jitterRand": 50
            },

            "createTpl": {
                "environment": "prod",
                "maxtps": "unlimited",
                "core": "empty",
                "credit": 32000
            }
        }

    def __init__(self, config_file=CONFIG_FILE, config=None, config_template=None, *args, **kwargs):
        self.config_file = config_file
        self.json = None
        self.config = config
        self.config_template = config_template

    def config_file_exists(self):
        """
        Returns true if the SoftHSMv1 config file exists
        :return:
        """
        return os.path.isfile(self.CONFIG_FILE)

    def load_config_file(self, config_file=None):
        """
        Tries to load & parse SoftHSMv1 config file
        If file does not exist or parsing failed exception is raised

        :param config_file:
        :return:
        """
        if config_file is not None:
            self.config_file = config_file
        if self.config_file is None:
            raise ValueError('Config file is None')

        with open(self.config_file, 'r') as f:
            read_lines = [x.strip() for x in f.read().split('\n')]
            lines = []
            for line in read_lines:
                if line.startswith('//'):
                    continue
                lines.append(line)

            self.json = json.loads(lines)

    def backup_current_config_file(self):
        """
        Copies current configuration file to a new file - backup.
        softhsm.conf -> 0001_softhsm.conf

        Used when generating a new SoftHSM configuration file, to
        preserve the old one if user accidentally reinitializes the system.
        :return:
        """
        cur_name = self.CONFIG_FILE
        with open(cur_name, 'r') as f:
            contents = f.read()

            fhnd, fname = util.unique_file(cur_name, 0o644)
            fhnd.write(contents)
            fhnd.close()
            return fname

    def configure(self, config=None):
        """
        Generates SoftHSMv1 configuration from the AMI config.
        :return:
        """
        if config is not None:
            self.config = config
        if self.config is None:
            raise ValueError('Configuration is not defined')

        slot_cfg = self.config_template if self.config_template is not None else self.DEFAULT_SLOT_CONFIG

        endpoint_process = config.resolve_endpoint(purpose=SERVER_PROCESS_DATA, protocol=PROTOCOL_RAW)[0]
        endpoint_enroll = config.resolve_endpoint(purpose=SERVER_ENROLLMENT, protocol=PROTOCOL_RAW)[0]
        if endpoint_process.host != endpoint_enroll.host:
            raise ValueError('Process host is different from the enrollment host. SoftHSM needs to be updated')

        slot_cfg['apikey'] = config.apikey
        slot_cfg['host'] = endpoint_process.host
        slot_cfg['port'] = endpoint_process.port
        slot_cfg['enrollPort'] = endpoint_enroll.port

        root = {'slots': [slot_cfg]}
        self.json = root
        pass

    def write_config(self):
        """
        Writes current configuration to the file.
        :return:
        """
        conf_name = self.CONFIG_FILE
        with os.fdopen(os.open(conf_name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644), 'w') as config_file:
            config_file.write('// \n')
            config_file.write('// SoftHSM configuration file for EnigmaBridge \n')
            config_file.write('// Config file generated: %s\n' % datetime.now().strftime("%Y-%m-%d %H:%M"))
            config_file.write('// \n')
            config_file.write(json.dumps(self.json, indent=2) + "\n\n")
        return conf_name




