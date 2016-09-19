from ebaws.consts import *
import json


class Core(object):

    @staticmethod
    def get_config_file_path():
        """Returns basic configuration file"""
        return CONFIG_DIR + '/' + CONFIG_FILE

    @staticmethod
    def get_config_file_lock_path():
        """PID of the process working on the file, exclusive write lock"""
        return CONFIG_DIR + '/' + CONFIG_FILE + '.pid'

