from ebaws.config import Config
from ebaws.consts import *
import json
import os.path
import util


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
    def backup_configuration(config):
        cur_name = Core.get_config_file_path()
        fhnd, fname = util.unique_file(cur_name, 0o644)
        fhnd.write(config.to_string()+"\n")
        return fname, fhnd




