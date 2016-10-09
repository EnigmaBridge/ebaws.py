##EnigmaBridge Amazon EC2 utils for EJBCA installation

This CLI installs a new EJBCA on EC2 instance. Specific AMI is required - with JBoss EAP installed.

## Troubleshooting
Error in installation of dependencies (cryptography, pyOpenSSL):
`sorry, but this version only supports 100 named groups` \[[100-named-groups]\]

Solution:
Install downgraded version of pycparser and pyOpenSSL:

```
pip install pycparser==2.13
pip install pyOpenSSL==0.13
pip install cryptography
```

You may need to install some deps for the python packages

```
yum install gcc g++ openssl-devel libffi-devel dialog
```

### SNI on Python < 2.7.9

TLS SNI support was added to Python. For earlier versions SNI needs to be added to Requests networking library.

```
pip install urllib3
pip install pyopenssl
pip install ndg-httpsclient
pip install pyasn1
```

### Mac OSX installation
For new OSX versions (El Capitan and above) the default system python installation
cannot be modified with standard means. There are some workarounds, but one can also use
`--user` switch for pip.

```
pip install --user cryptography
```

[100-named-groups]: https://community.letsencrypt.org/t/certbot-auto-fails-while-setting-up-virtual-environment-complains-about-package-hashes/20529/18

