import logging
from config import Config
from core import Core
from errors import *
import requests
import util
import re
import consts
import OpenSSL
import json
import base64
from datetime import datetime
from ebclient.eb_configuration import *
from ebclient.eb_registration import *
from ebclient.registration import *
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


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
    AMI_KEY_PUBLIC_HOSTNAME = 'public-hostname'

    AMI_KEYS = [AMI_KEY_ID, AMI_KEY_INSTANCE_ID, AMI_KEY_INSTANCE_TYPE, AMI_KEY_PLACEMENT, AMI_KEY_PRODUCT_CODES,
                AMI_KEY_PUBLIC_IP, AMI_KEY_LOCAL_IP, AMI_KEY_PUBLIC_HOSTNAME]

    def __init__(self, *args, **kwargs):
        self.ami_id = None
        self.ami_instance_id = None
        self.ami_instance_type = None
        self.ami_placement = None
        self.ami_product_code = None
        self.ami_results = None
        self.ami_public_ip = None
        self.ami_local_ip = None
        self.ami_public_hostname = None
        self.ec2_metadata_executable = None

    def env_check(self):
        for candidate in consts.EC2META_FILES:
            if util.exe_exists(candidate):
                self.ec2_metadata_executable = candidate
        if self.ec2_metadata_executable is None:
            raise EnvError('ec2-metadata executable was not found')

    def load(self):
        self.env_check()

        # removed options:
        # -o local ip
        # -c product codes
        out, err = util.run_script([self.ec2_metadata_executable] + ('-a -i -t -z -v -p'.split(' ')))

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
            elif c_key == self.AMI_KEY_PUBLIC_HOSTNAME:
                self.ami_public_hostname = c_val
        pass


class Registration(object):
    """
    Takes care about registration process
    """
    def __init__(self, email=None, eb_config=None, config=None, debug=False, *args, **kwargs):
        self.email = email
        self.debug = debug
        self.eb_config = eb_config
        self.config = config
        self.key = None
        self.crt = None
        self.key_path = None
        self.crt_path = None

        self.crt_pem = None
        self.key_pem = None
        self.key_py = None
        self.key_crypto = None
        self.crt_crypto = None

        self.info_loader = InfoLoader()
        self.info_loader.load()
        pass

    def new_identity(self, identities=None, id_dir=consts.CONFIG_DIR, backup_dir=consts.CONFIG_DIR_OLD):
        """
        New identity - key pair for domain claim
        """
        util.make_or_verify_dir(id_dir, mode=0o755)
        util.make_or_verify_dir(backup_dir, mode=0o755)

        self.key_path = os.path.join(id_dir, consts.IDENTITY_KEY)
        self.crt_path = os.path.join(id_dir, consts.IDENTITY_CRT)
        util.delete_file_backup(self.key_path, 0o600, backup_dir=backup_dir)
        util.delete_file_backup(self.crt_path, 0o600, backup_dir=backup_dir)

        # Generate new private key, 2048bit
        self.key = OpenSSL.crypto.PKey()
        self.key.generate_key(OpenSSL.crypto.TYPE_RSA, 2048)
        self.key_pem = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, self.key)
        self.key_crypto = util.load_pem_private_key(self.key_pem)
        self.key_py = util.load_pem_private_key_pycrypto(self.key_pem)

        # Generate certificate
        id_to_use = identities if identities is not None else [self.info_loader.ami_instance_id]
        self.crt = util.gen_ss_cert(self.key, id_to_use, validity=(25 * 365 * 24 * 60 * 60))
        self.crt_pem = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, self.crt)
        self.crt_crypto = util.load_x509(self.crt_pem)

        with util.safe_open(self.crt_path, 'wb', chmod=0o600) as crt_file:
            crt_file.write(self.crt_pem)
        with util.safe_open(self.key_path, 'wb', chmod=0o600) as key_file:
            key_file.write(self.key_pem)

        return self.key, self.crt, self.key_path, self.crt_path

    def load_identity(self, id_dir=consts.CONFIG_DIR):
        """
        Loads identity from the directory
        """
        self.key_path = os.path.join(id_dir, consts.IDENTITY_KEY)
        self.crt_path = os.path.join(id_dir, consts.IDENTITY_CRT)

        if not os.path.exists(self.key_path):
            return None

        with open(self.key_path, mode='r') as key:
            self.key_pem = key.read()
            self.key = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, self.key_pem)
            self.key_crypto = util.load_pem_private_key(self.key_pem)
            self.key_py = util.load_pem_private_key_pycrypto(self.key_pem)

        with open(self.crt_path, mode='r') as crt:
            self.crt_pem = crt.read()
            self.crt = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, self.crt_pem)
            self.crt_crypto = util.load_x509(self.crt_pem)

        return 0

    def new_registration(self):
        """
        Creates a new registration, returns new configuration object
        """
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
        self.config.email = self.email
        self.config.username = regresponse['username']
        self.config.password = regresponse['password']
        self.config.apikey = apiresponse['apikey']
        self.config.servers = apiresponse['servers']
        self.config.generated_time = (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
        return self.config

    def new_domain(self):
        """
        Enrols for a new AWS domain
        :return:
        """
        api_data_reg = {
            'username': self.config.username,
            'apikey': self.config.apikey,
            'certificate': self.get_cert_pem_json()
        }

        req = EnrolDomainRequest(api_data=api_data_reg, env=ENVIRONMENT_DEVELOPMENT, config=self.eb_config)
        try:
            resp = req.call()
        except Exception as e:
            print api_data_reg
            print req.response
            raise

        if resp is None:
            raise InvalidResponse('Response is invalid')

        if 'domain' not in resp:
            raise InvalidResponse('Domain was not present in the response')

        # Step 3: save new identity configuration
        self.config.nsdomain = resp['domain']
        return self.config

    def refresh_domain(self):
        """
        Attempts to refresh previously assigned domain after AWS restart
        :return:
        """
        api_data_req_body = {
            'ipv4': self.info_loader.ami_public_ip,
            'username': self.config.username,
            'apikey': self.config.apikey
        }

        req = GetDomainChallengeRequest(api_data=api_data_req_body, env=ENVIRONMENT_DEVELOPMENT, config=self.eb_config)
        resp = req.call()

        if 'authentication' not in resp:
            raise InvalidResponse('Authentication not present in the response')

        auth_type = resp['authentication']
        if auth_type not in ['signature', 'challenge'] :
            raise InvalidResponse('Unsupported authentication type ' + auth_type)

        # Step 2 - claim the domain
        challenge_response = resp['challenge']
        api_data_req = {
            'username': self.config.username,
            'apikey': self.config.apikey,
            'authentication': auth_type,
            'response': challenge_response
        }

        payload = base64.b64encode(json.dumps(api_data_req))
        signer = self.key_crypto.signer(padding=padding.PKCS1v15(), algorithm=hashes.SHA256())
        signer.update(payload)
        signature = base64.b64encode(signer.finalize())

        signature_aux = {
            'signature': {
                'payload': payload,
                'value': signature
            },
        }

        req_upd = UpdateDomainRequest(api_data=api_data_req, env=ENVIRONMENT_DEVELOPMENT, config=self.eb_config)
        req_upd.aux_data = signature_aux

        try:
            resp_update = req_upd.call()
        except Exception as e:
            if self.debug:
                print api_data_req_body
                print signature_aux
                print req_upd.response
                print req_upd.request.body
            raise

        if 'domains' not in resp_update:
            raise InvalidResponse('domains not in the response')

        # Sort the domains by the key (length, lexicographic)
        domains = resp_update['domains']
        domains.sort()
        domains.sort(key=len, reverse=True)

        self.config.domains = domains
        self.config.last_ipv4 = self.info_loader.ami_public_ip
        return self.config

    def get_cert_pem_json(self):
        result = ''
        for line in self.crt_pem.split('\n'):
            line = line.strip()
            if line.startswith('---'):
                continue
            result += line
        return result

