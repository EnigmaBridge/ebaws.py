import json
import functools

__author__ = 'dusanklinec'


class Config(object):
    """Configuration object, handles file read/write"""

    def __init__(self, json=None, *args, **kwargs):
        self.json = json
        pass

    @classmethod
    def from_json(cls, json_string):
        return cls(json=json.loads(json_string))

    @classmethod
    def from_file(cls, file_name):
        with open(file_name, 'r') as f:
            conf_data = f.read()
            return Config.from_json(conf_data)

    def ensure_config(self):
        if self.json is None:
            self.json = {}
        if 'config' not in self.json:
            self.json['config'] = {}

    def has_nonempty_config(self):
        return self.json is not None and 'config' in self.json and len(self.json['config']) > 0

    def get_config(self, key):
        if not self.has_nonempty_config():
            return None
        return self.json['config'][key] if key in self.json['config'] else None

    def set_config(self, key, val):
        self.ensure_config()
        self.json['config'][key] = val

    def has_identity(self):
        return self.username is not None

    def has_apikey(self):
        return self.apikey is not None

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
    def endpoint_process(self):
        return self.get_config('endpoint_process')

    @endpoint_process.setter
    def endpoint_process(self, val):
        self.set_config('endpoint_process', val)

    # enroll endpoint
    @property
    def endpoint_enroll(self):
        return self.get_config('endpoint_enroll')

    @endpoint_enroll.setter
    def endpoint_enroll(self, val):
        self.set_config('endpoint_enroll', val)



