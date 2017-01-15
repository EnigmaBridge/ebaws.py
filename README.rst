EnigmaBridge Amazon EC2 utils for PKI
=====================================

This CLI setups a new fresh EJBCA (PKI) installation on EC2 instance
with a new `EnigmaBridge <https://enigmabridge.com>`__ identity.
`EnigmaBridge <https://enigmabridge.com>`__ is integrated with EJBCA as
a new PKCS#11 crypto token, you can start using it to securely store
your root CA keys.

The cli looks like the following:

::

    --------------------------------------------------------------------------------
        Enigma Bridge AWS command line interface (v0.0.14) 

        usage - shows simple command list
        init  - initializes the key management system

        More info: https://enigmabridge.com/amazonpki 
    --------------------------------------------------------------------------------
    $> 

Specific AMI is required - with JBoss EAP & EJBCA installed. More
information on image setup can be found in
`IMG-INSTALL <https://github.com/EnigmaBridge/ebaws.py/blob/master/IMG-INSTALL.md>`__
page.

For info on the network communication flow during the installation
please refer to
`connections <https://github.com/EnigmaBridge/ebaws.py/blob/master/connections.md>`__
page.

Features
========

-  EJBCA 6.3.1.1
-  JBoss EAP 6.4
-  SoftHSMv1-EnigmaBridge PKCS#11 adapter
-  EnigmaBridge Dynamic DNS for AWS

SoftHSMv1-EnigmaBridge PKCS#11 adapter
--------------------------------------

`SoftHSMv1-EB <https://github.com/EnigmaBridge/SoftHSMv1>`__ is a
PKCS#11 interface for `EnigmaBridge <https://enigmabridge.com>`__
services. Using this adapter one can use our services using the generic
PKCS#11 interface without need to modify the software.

Like in EJBCA case, there is no need to modify the software which
supports PKCS#11, just plug our adapter to it and it starts working.

One can for example generate RSA keys via PKCS#11 adapter and call
encrypt, decrypt, sign, verify operations on it. The keys are securely
stored on EnigmaBridge servers, in the secure hardware. The
cryptographic operation itself is performed in the secure hardware in a
transparent way.

Dynamic DNS
-----------

Amazon provides IP address to your EC2 instance from the IP pool. This
kind of address is re-allocated after your instance is turned off. After
next start it will get a new IP address.

Usually its convenient to have a static IP so you can map it to the
domain name or put in the config files, manuals, etc... You can buy
Amazon Elastic IP which remains static even after instance restart or
you can use our `EnigmaBridge <https://enigmabridge.com>`__ Dynamic DNS
feature for the AWS.

During the initialization we allocate a new domains for your running
instance, e.g., sunderland1.pki.enigmabridge.com. It has A record
pointing to your current IP address.

After you restart your instance, our script is started. It connects to
our DNS server and updates the A record for your domain in a secure way
- request is signed with the key generated when domain was created.

Time to live of the record is 600 seconds so after the restart the
hostname is updated in 10 minutes.

In this way you will get the static DNS name even if your IP changes.

Requirements
============

Generally the host need to have TCP port 443 open for LetsEncrypt domain
verification. Without that you won't get valid SSL certificate for your
CA domain and you won't be able to access administration console of your
EJBCA installation in a secure way.

The EJBCA itself runs on TCP port 8443. It depends on you how you set
it. It don't necessarily have to be open to the world-fine. Its enough
if you can access it somehow. e.g., it's possible to access EJBCA admin
via SSH tunnel. ``ssh -L 8443:localhost:8443 ami_ip``

Init
====

The init command starts a new fresh installation. If a previous
installation is present it asks user whether to proceed, backups the old
installation databases and config files and installs a new one.

The installation process looks like this:

::

    --------------------------------------------------------------------------------
        Enigma Bridge AWS command line interface (v0.0.14) 

        usage - shows simple command list
        init  - initializes the key management system

        More info: https://enigmabridge.com/amazonpki 
    --------------------------------------------------------------------------------
    $> init
    Going to install PKI system and enrol it to the Enigma Bridge FIPS140-2 encryption service.

    We need your email address for:
       a) identity verification in case of a recovery / support 
       b) LetsEncrypt certificate registration
    It's optional but we highly recommend to enter a valid e-mail address (especially on a production system)

    Please enter your email address [empty]: tester@enigmabridge.com
    Is this email correct? 'tester@enigmabridge.com' (Y/n):y

    Checking if port 443 is open for LetsEncrypt, ip: 52.212.77.52

    New domains registered for this host: 
      - sunderland1.pki.enigmabridge.com
      - sr1.pki.enigmabridge.com

    New configuration was written to: /etc/enigma/config.json

    SoftHSMv1 configuration has been backed up to: None
    New SoftHSMv1 configuration has been written to: /etc/softhsm.conf

    SoftHSMv1 previous token database moved to: /var/lib/softhsm.old/softhsm_0018
    SoftHSMv1 initialization: The token has been initialized.

    Going to install PKI system
      This may take 15 minutes or less. Please, do not interrupt the installation
      and wait until the process completes.

     - Updating settings

     - Restarting application server, please wait...
    .........
     - Preparing environment for application server
    ...................
     - Restarting application server, please wait...
    ...
     - Deploying the PKI system
    ................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................
     - Installing the PKI system
    .......................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................
    PKI installed successfully.

    Going to generate EnigmaBridge keys in the crypto token:
    ..................
    EnigmaBridge tokens generated successfully
    You can use these newly generated keys for your CA or generate another ones with:
      sudo -E -H -u jboss /opt/ejbca_ce_6_3_1_1/bin/pkcs11HSM.sh generate /usr/lib64/softhsm/libsofthsm.so 2048 signKey 0
      sudo -E -H -u jboss /opt/ejbca_ce_6_3_1_1/bin/pkcs11HSM.sh generate /usr/lib64/softhsm/libsofthsm.so 2048 defaultKey 0
      sudo -E -H -u jboss /opt/ejbca_ce_6_3_1_1/bin/pkcs11HSM.sh generate /usr/lib64/softhsm/libsofthsm.so 1024 testKey 0

    Adding an EnigmaBridge crypto token to your PKI instance:
    .
    EnigmaBridgeToken added to the PKI instance

    Installing LetsEncrypt certificate for: sunderland1.pki.enigmabridge.com, sr1.pki.enigmabridge.com
    ....
    Publicly trusted certificate installed (issued by LetsEncrypt

    --------------------------------------------------------------------------------



    [OK] System installation is completed



    --------------------------------------------------------------------------------

    Please setup your computer for secure connections to your PKI key management system:

    Download p12 file: /home/ec2-user/ejbca-admin.p12
      scp -i <your_Amazon_PEM_key> ec2-user@sunderland1.pki.enigmabridge.com:/home/ec2-user/ejbca-admin.p12 .
      Key import password is: g5Bkg79Lvk3Q8jVC

    The following page can guide you through p12 import: https://enigmabridge.com/support/aws13076
    Once you import the p12 file to your computer browser/keychain you can connect to the PKI admin interface:
      https://sunderland1.pki.enigmabridge.com:8443/ejbca/adminweb/
      https://sr1.pki.enigmabridge.com:8443/ejbca/adminweb/

Troubleshooting
===============

Error in installation of dependencies (cryptography, pyOpenSSL):
``sorry, but this version only supports 100 named groups``
[`100-named-groups <https://community.letsencrypt.org/t/certbot-auto-fails-while-setting-up-virtual-environment-complains-about-package-hashes/20529/18>`__]

Solution: Install downgraded version of pycparser and pyOpenSSL:

::

    pip install pycparser==2.13
    pip install pyOpenSSL==0.13
    pip install cryptography

You may need to install some deps for the python packages

::

    yum install gcc g++ openssl-devel libffi-devel dialog

SNI on Python < 2.7.9
---------------------

TLS SNI support was added to Python. For earlier versions SNI needs to
be added to Requests networking library.

::

    pip install urllib3
    pip install pyopenssl
    pip install ndg-httpsclient
    pip install pyasn1

Mac OSX installation
--------------------

For new OSX versions (El Capitan and above) the default system python
installation cannot be modified with standard means. There are some
workarounds, but one can also use ``--user`` switch for pip.

::

    pip install --user cryptography