import logging
from config import Config
from core import Core
from errors import *
import requests
import util
import re
import consts
from datetime import datetime
from ebclient.eb_configuration import *
from ebclient.eb_registration import *
from ebclient.registration import *


__author__ = 'dusanklinec'


logger = logging.getLogger(__name__)


class InfoLoader(object):
    """
    Loads information from the system
    """

    AMI_KEY_ID = 'ami-id'
    AMI_KEY_INSTANCE_ID = 'instance-id'
    AMI_KEY_INSTANCE_TYPE = 'instance-type'
    AMI_KEY_PLACEMENT = 'placement'
    AMI_KEY_PRODUCT_CODES = 'product-codes'
    AMI_KEY_PUBLIC_IP = 'public-ipv4'
    AMI_KEY_LOCAL_IP = 'local-ipv4'

    AMI_KEYS = [AMI_KEY_ID, AMI_KEY_INSTANCE_ID, AMI_KEY_INSTANCE_TYPE, AMI_KEY_PLACEMENT, AMI_KEY_PRODUCT_CODES,
                AMI_KEY_PUBLIC_IP, AMI_KEY_LOCAL_IP]

    def __init__(self, *args, **kwargs):
        self.ami_id = None
        self.ami_instance_id = None
        self.ami_instance_type = None
        self.ami_placement = None
        self.ami_product_code = None
        self.ami_results = None
        self.ami_public_ip = None
        self.ami_local_ip = None
        self.ec2_metadata_executable = None

    def env_check(self):
        for candidate in consts.EC2META_FILES:
            if util.exe_exists(candidate):
                self.ec2_metadata_executable = candidate
        if self.ec2_metadata_executable is None:
            raise EnvError('ec2-metadata executable was not found')

    def load(self):
        self.env_check()
        out, err = util.run_script([self.ec2_metadata_executable] + ('-a -i -t -z -c -v -o -p'.split(' ')))

        lines = [x.strip() for x in out.split('\n')]
        self.ami_results = {}
        for line in lines:
            if len(line) == 0:
                continue

            match = re.match(r'^\s*([a-zA-Z0-9-\s]+?)\s*:(.+)\s*$', line, re.I)
            if match is None:
                continue

            c_key = match.group(1).strip()
            c_val = match.group(2).strip()
            self.ami_results[c_key] = c_val

            if c_key == self.AMI_KEY_ID:
                self.ami_id = c_val
            elif c_key == self.AMI_KEY_INSTANCE_ID:
                self.ami_instance_id = c_val
            elif c_key == self.AMI_KEY_INSTANCE_TYPE:
                self.ami_instance_type = c_val
            elif c_key == self.AMI_KEY_PLACEMENT:
                self.ami_placement = c_val
            elif c_key == self.AMI_KEY_PRODUCT_CODES:
                self.ami_product_code = c_val
            elif c_key == self.AMI_KEY_LOCAL_IP:
                self.ami_local_ip = c_val
            elif c_key == self.AMI_KEY_PUBLIC_IP:
                self.ami_public_ip = c_val
        pass


class Registration(object):
    """
    Takes care about registration process
    """
    def __init__(self, email=None, eb_config=None, *args, **kwargs):
        self.email = None
        self.eb_config = None
        self.config = None
        self.info_loader = InfoLoader()
        pass

    def new_registration(self):
        """
        Creates a new registration, returns new configuration object
        """
        self.info_loader.load()
        if self.info_loader.ami_instance_id is None:
            raise EnvError('Could not extract AMI instance ID')

        # Step 1: create a new identity
        if self.eb_config is None:
            self.eb_config = Core.get_default_eb_config()

        client_data_reg = {
            'name': self.info_loader.ami_instance_id,
            'authentication': 'type',
            'type': 'test',
            'token': 'LSQJCHT61VTEMFQBZADO',
            'ami': self.info_loader.ami_results,
            'email': self.email
        }

        regreq = RegistrationRequest(client_data=client_data_reg, env=ENVIRONMENT_DEVELOPMENT, config=self.eb_config)
        regresponse = regreq.call()

        if 'username' not in regresponse:
            raise InvalidResponse('Username was not present in the response')

        # Step 2: ask for API key
        client_api_req = {
            'authentication': 'password',
            'username': regresponse['username'],
            'password': regresponse['password']
        }

        endpoint = {
            "ipv4": "123.23.23.23",
            "ipv6": "fe80::2e0:4cff:fe68:bcc2/64",
            "country": "gb",
            "network": "plusnet",
            "location": [0.34,10]
        }

        apireq = ApiKeyRequest(client_data=client_api_req, endpoint=endpoint, env=ENVIRONMENT_DEVELOPMENT, config=self.eb_config)
        apiresponse = apireq.call()

        if 'apikey' not in apiresponse:
            raise InvalidResponse('ApiKey was not present in the getApiKey response')

        # Step 3: save new identity configuration
        self.config = Config(eb_config=self.eb_config)
        self.config.username = regresponse['username']
        self.config.password = regresponse['password']
        self.config.apikey = apiresponse['apikey']
        self.config.servers = apiresponse['servers']
        self.config.generated_time = (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
        return self.config




