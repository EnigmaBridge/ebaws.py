from config import Config
from consts import *
from ebclient import eb_configuration
import json
import os.path
import util
from datetime import datetime


class Core(object):

    @staticmethod
    def get_config_file_path():
        """Returns basic configuration file"""
        return CONFIG_DIR + '/' + CONFIG_FILE

    @staticmethod
    def get_config_file_lock_path():
        """PID of the process working on the file, exclusive write lock"""
        return CONFIG_DIR + '/' + CONFIG_FILE + '.pid'

    @staticmethod
    def config_file_exists():
        conf_name = Core.get_config_file_path()
        return os.path.isfile(conf_name)

    @staticmethod
    def is_configuration_nonempty(config):
        return config is not None and config.has_nonempty_config()

    @staticmethod
    def read_configuration():
        if not Core.config_file_exists():
            return None

        conf_name = Core.get_config_file_path()
        return Config.from_file(conf_name)

    @staticmethod
    def write_configuration(cfg):
        util.make_or_verify_dir(CONFIG_DIR, mode=0o755)

        conf_name = Core.get_config_file_path()
        with os.fdopen(os.open(conf_name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as config_file:
            config_file.write('// \n')
            config_file.write('// Config file generated: %s\n' % datetime.now().strftime("%Y-%m-%d %H:%M"))
            config_file.write('// \n')
            config_file.write(cfg.to_string() + "\n\n")
        return conf_name

    @staticmethod
    def backup_configuration(config):
        cur_name = Core.get_config_file_path()
        if os.path.exists(cur_name):
            util.make_or_verify_dir(CONFIG_DIR_OLD, mode=0o644)

            opath, otail = os.path.split(cur_name)
            backup_path = os.path.join(CONFIG_DIR_OLD, otail)

            fhnd, fname = util.unique_file(backup_path, 0o644)
            with fhnd:
                fhnd.write(config.to_string()+"\n")
            return fname

    @staticmethod
    def get_default_eb_config():
        """
        Returns default configuration for the EB client
        :return:
        """
        cfg = eb_configuration.Configuration()
        cfg.endpoint_register = eb_configuration.Endpoint.url('https://hut6.enigmabridge.com:8445')
        return cfg


