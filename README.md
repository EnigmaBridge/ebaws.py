##EnigmaBridge Amazon EC2 utils for EJBCA installation

This CLI installs a new EJBCA on EC2 instance. Specific AMI is required - with JBoss EAP installed.

## Troubleshooting
Error in installation of dependencies (cryptography, pyOpenSSL):
Install downgraded version of pycparser and pyOpenSSL:

```
pip install pycparser==2.13
pip install pyOpenSSL==0.13
pip install cryptography
```


