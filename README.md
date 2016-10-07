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


[100-named-groups]: https://community.letsencrypt.org/t/certbot-auto-fails-while-setting-up-virtual-environment-complains-about-package-hashes/20529/18

