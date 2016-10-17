##EnigmaBridge Amazon EC2 utils for PKI

This CLI setups a new fresh EJBCA (PKI) installation on EC2 instance with a new [EnigmaBridge] identity.
[EnigmaBridge] is integrated with EJBCA as a new PKCS#11 crypto token, you can start using it
to securely store your root CA keys.

The cli looks like the following:
```
--------------------------------------------------------------------------------
    Enigma Bridge AWS command line interface (v0.0.12) 

    usage - shows simple command list
    init  - initializes the key management system

    More info: https://enigmabridge.com/amazonpki 
--------------------------------------------------------------------------------
$> 
```

Specific AMI is required - with JBoss EAP & EJBCA installed.
More information on image setup can be found in [IMG-INSTALL] page.

## Init
The init command starts a new fresh installation. If a previous installation is present
it asks user whether to proceed, backups the old installation databases and config files
and installs a new one.

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
[IMG-INSTALL]: https://github.com/EnigmaBridge/ebaws.py/blob/master/IMG-INSTALL.md
[EnigmaBridge]: https://enigmabridge.com

