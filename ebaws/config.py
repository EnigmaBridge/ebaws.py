import json
import functools
from consts import *
from errors import *
from ebclient.eb_configuration import Endpoint
from ebclient.registration import *

__author__ = 'dusanklinec'


class EBEndpoint(Endpoint):
    """
    Extends normal endpoint, with added reference to the configuration
    """
    def __init__(self, scheme=None, host=None, port=None, server=None, *args, **kwargs):
        super(EBEndpoint, self).__init__(
            scheme=scheme,
            host=host,
            port=port)
        self.server = server


class Config(object):
    """Configuration object, handles file read/write"""

    def __init__(self, json_db=None, eb_config=None, *args, **kwargs):
        self.json = json_db
        self.eb_config = eb_config

        pass

    @classmethod
    def from_json(cls, json_string):
        return cls(json_db=json.loads(json_string))

    @classmethod
    def from_file(cls, file_name):
        with open(file_name, 'r') as f:
            read_lines = [x.strip() for x in f.read().split('\n')]
            lines = []
            for line in read_lines:
                if line.startswith('//'):
                    continue
                lines.append(line)

            return Config.from_json('\n'.join(lines))

    def ensure_config(self):
        if self.json is None:
            self.json = {}
        if 'config' not in self.json:
            self.json['config'] = {}

    def has_nonempty_config(self):
        return self.json is not None and 'config' in self.json and len(self.json['config']) > 0

    def get_config(self, key, default=None):
        if not self.has_nonempty_config():
            return default
        return self.json['config'][key] if key in self.json['config'] else default

    def set_config(self, key, val):
        self.ensure_config()
        self.json['config'][key] = val

    def has_identity(self):
        return self.username is not None

    def has_apikey(self):
        return self.apikey is not None

    def to_string(self):
        return json.dumps(self.json, indent=2) if self.has_nonempty_config() else ""

    def resolve_endpoint(self, purpose=SERVER_PROCESS_DATA, protocol=PROTOCOL_HTTPS, environment=None, *args, **kwargs):
        """
        Resolves required endpoint from the configuration according to the parameters
        :param purpose:
        :param protocol:
        :return:
        """
        if not self.has_nonempty_config() or self.servers is None:
            raise ValueError('Configuration has no servers')

        candidate_list = []
        for server in self.servers:
            endpoint_key = 'useEndpoints'
            if purpose == SERVER_ENROLLMENT:
                endpoint_key = 'enrolEndpoints'
            elif purpose == SERVER_REGISTRATION:
                endpoint_key = 'registerEndpoints'
            elif purpose != SERVER_PROCESS_DATA:
                raise ValueError('Endpoint purpose unknown')

            if endpoint_key not in server:
                continue
            if environment is not None and server['environment'] != environment:
                continue

            endpoints = server[endpoint_key]
            for endpoint in endpoints:
                if protocol is not None and endpoint['protocol'] != protocol:
                    continue

                # Construct a candidate
                candidate = EBEndpoint(scheme=endpoint['protocol'],
                                       host=server['fqdn'],
                                       port=endpoint['port'],
                                       server=server)

                candidate_list.append(candidate)
            pass

        if len(candidate_list) == 0:
            raise NoSuchEndpoint('No such endpoint found')

        return candidate_list[0], candidate_list

    # email
    @property
    def email(self):
        return self.get_config('email')

    @email.setter
    def email(self, val):
        self.set_config('email', val)

    # username
    @property
    def username(self):
        return self.get_config('username')

    @username.setter
    def username(self, val):
        self.set_config('username', val)

    # password
    @property
    def password(self):
        return self.get_config('password')

    @password.setter
    def password(self, val):
        self.set_config('password', val)

    # apikey
    @property
    def apikey(self):
        return self.get_config('apikey')

    @apikey.setter
    def apikey(self, val):
        self.set_config('apikey', val)

    # process endpoint
    @property
    def servers(self):
        return self.get_config('servers')

    @servers.setter
    def servers(self, val):
        self.set_config('servers', val)

    # Time the configuration was generated
    @property
    def generated_time(self):
        return self.get_config('generated_time')

    @generated_time.setter
    def generated_time(self, val):
        self.set_config('generated_time', val)

    # NS domain
    @property
    def nsdomain(self):
        return self.get_config('nsdomain')

    @nsdomain.setter
    def nsdomain(self, val):
        self.set_config('nsdomain', val)

    # DNS domains
    @property
    def domains(self):
        return self.get_config('domains')

    @domains.setter
    def domains(self, val):
        self.set_config('domains', val)

    # EJBCA hostname
    @property
    def ejbca_hostname(self):
        return self.get_config('ejbca_hostname')

    @ejbca_hostname.setter
    def ejbca_hostname(self, val):
        self.set_config('ejbca_hostname', val)

    # EJBCA LE domains
    @property
    def ejbca_domains(self):
        return self.get_config('ejbca_domains')

    @ejbca_domains.setter
    def ejbca_domains(self, val):
        self.set_config('ejbca_domains', val)

    # EJBCA key store password
    @property
    def ejbca_jks_password(self):
        return self.get_config('ejbca_jks_password')

    @ejbca_jks_password.setter
    def ejbca_jks_password(self, val):
        self.set_config('ejbca_jks_password', val)

    # EJBCA custom hostname flag
    @property
    def ejbca_hostname_custom(self):
        return self.get_config('ejbca_hostname_custom', default=False)

    @ejbca_hostname_custom.setter
    def ejbca_hostname_custom(self, val):
        self.set_config('ejbca_hostname_custom', val)

    # Last public IPV4 used by EJBCA domain
    @property
    def last_ipv4(self):
        return self.get_config('last_ipv4')

    @last_ipv4.setter
    def last_ipv4(self, val):
        self.set_config('last_ipv4', val)

    # process endpoint
    @property
    def endpoint_process(self):
        return self.resolve_endpoint(SERVER_PROCESS_DATA, PROTOCOL_HTTPS)

    # enroll endpoint
    @property
    def endpoint_enroll(self):
        return self.resolve_endpoint(SERVER_ENROLLMENT, PROTOCOL_HTTPS)



