# Image preparation

Brief outline of the installation of the base AWS image needed for ebaws.py to work.

* Install JBoss EAP 6.4.0
* Install [EJBCA] 6.3.1.1
* Install [SoftHSM-EB] from RPMs

## JBoss installation

* Download JBoss EAP installator
* Add jboss user
* chown
* Setup `/etc/init.d/` script
* Start JBoss after start

You can follow this [installation-tutorial].

## JBoss configuration

Enable PKCS#11 support in the JBoss. Edit the following file and add new entries below.
`/opt/jboss-eap-6.4.0/modules/system/layers/base/sun/jdk/main/module.xml`:

```xml
<path name="sun/security/x509"/>
<path name="sun/security/pkcs11"/>
<path name="sun/security/pkcs11/wrapper"/>
```

## EJBCA 

* Download [EJBCA]
* Copy installation to `/opt/ejbca_ce_6_3_1_1`
* `chown -R jboss:jboss /opt/ejbca_ce_6_3_1_1`
* Apply patches from this repository `assets/ejbca_patches`. [Quilt] patch system is used for this.
  * Patch for automatic installation is included - password entry from command line (Python installer)
  * Reinforced JBoss reload ant script with retry mechanism as it could fail due to JBoss CLI error.

## Configure environment

`/etc/profile.d/ejbca.sh`:

```
export EJBCA_HOME=/opt/ejbca_ce_6_3_1_1
```

`/etc/profile.d/jboss.sh`:

```
export JBOSS_HOME=/opt/jboss-eap-6.4.0
```

## JBoss redirect

Redirecting `/` context-root to the `/ejbca` for the user friendliness.

```xml
<subsystem xmlns="urn:jboss:domain:web:2.2" default-virtual-server="default-host" native="false">
    <virtual-server name="default-host" enable-welcome-root="true">
        <alias name="localhost"/>
        <rewrite pattern="^/$" substitution="/test" flags="L,QSA,R" />
    </virtual-server>
</subsystem>
```



## Wrapper script
Install `ebaws.sh` as a `/usr/sbin/ebaws`


## Minor settings

### Motd 
Copy `assets/motd/35-banner-eb` to `/etc/update-motd.d/35-banner-eb`


## Troubleshooting

### Botan installation
Botan is SoftHSM-EB dependency and can be installed from the EPEL.
The minimal version: `botan.x86_64.1.10.13-1.el7`.

### Botan installation from sources

```bash
# deps
yum install gcc-c++ sqlite sqlite-devel
 
# Botan install
wget http://botan.randombit.net/releases/Botan-1.10.12.tgz && \
tar -xzvf Botan-1.10.12.tgz                                && \
cd Botan-1.10.12                                           && \
./configure.py --prefix=$HOME/botan                        && \
make                                                       && \
make install                                               && \
echo -e "[\E[32m\033[1m OK \033[0m] Botan install Success" || \
(echo -e "[\E[31m\033[1mFAIL\033[0m] Botan install Failed" && \
exit 1)
 
 
# Botan lib reachable by dynamic loader
echo '/usr/local/lib' > /etc/ld.so.conf.d/local.conf
ldconfig # to refresh ld cache
``` 


[installation-tutorial]: https://www.rosehosting.com/blog/installing-and-setting-up-java-jboss-7-final-on-a-centos-6-linux-vps/
[SoftHSM-EB]: https://github.com/EnigmaBridge/SoftHSMv1/releases
[EJBCA]: https://www.ejbca.org/download.html
[Quilt]: https://en.wikipedia.org/wiki/Quilt_(software)

