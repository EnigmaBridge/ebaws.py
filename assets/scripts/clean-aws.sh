#!/usr/bin/env bash

# ec2-user
/bin/rm /home/ec2-user/.jboss-cli-history
/bin/rm /home/ec2-user/.viminfo
echo -n '' > /home/ec2-user/.bash_history
/bin/rm -rf /home/ec2-user/.config/*
/bin/rm -rf /home/ec2-user/.config/*
/bin/rm -rf /home/ec2-user/.cache/pip
/bin/rm -rf /home/ec2-user/ebaws.py

# root
/bin/rm /root/.jboss-cli-history
/bin/rm /root/.viminfo
echo -n '' > /root/.bash_history
find /root/.*history /home/*/.*history -exec rm -f {} \;

# Logs
echo -n '' > /var/log/jboss-console.log
echo -n '' > /var/log/messages
echo -n '' > /var/log/maillog
echo -n '' > /var/log/secure
echo -n '' > /var/log/yum.log
echo -n '' > /var/log/lastlog
echo -n '' > /var/log/wtmp
echo -n '' > /var/log/btmp
echo -n '' > /var/log/dmesg
echo -n '' > /var/log/dmesg.old
echo -n '' > /var/log/cron
echo -n '' > /var/log/cloud-init.log
echo -n '' > /var/log/cloud-init-output.log
echo -n '' > /var/log/dracut.log
echo -n '' > /var/log/audit/audit.log
/bin/rm /var/log/audit/audit.log.*

sudo passwd -l root
shred -u ~/.*history

#
# Enigma related
#
find /var/lib/softhsm -type f -exec shred -u {} \;
find /var/lib/softhsm.old -type f -exec shred -u {} \;
find /etc/enigma -type f -exec shred -u {} \;
find /etc/enigma.old -type f -exec shred -u {} \;
find /etc/softhsm.old -type f -exec shred -u {} \;
find /root/ejbca.passwords -type f -exec shred -u {} \;
find /root/ejbca.passwords.old -type f -exec shred -u {} \;
find /root/ejbcadb.old -type f -exec shred -u {} \;
/bin/rm /etc/softhsm.conf

find /opt/ejbca_ce_6_3_1_1/conf/ -type f -name 'web_0*.properties' -exec shred -u {} \;
find /opt/ejbca_ce_6_3_1_1/conf/ -type f -name 'install_0*.properties' -exec shred -u {} \;

/bin/rm /opt/ejbca_ce_6_3_1_1/conf/web.properties
/bin/rm /opt/ejbca_ce_6_3_1_1/conf/install.properties
/bin/rm -rf /var/softhsm
/bin/rm -rf /var/lib/softhsm
/bin/rm -rf /var/lib/softhsm.*
/bin/rm -rf /etc/enigma/*
/bin/rm -rf /etc/enigma.old
/bin/rm -rf /etc/softhsm.old
/bin/rm -rf /root/ejbca*
/bin/rm -rf /root/ejbca.passwords*
/bin/rm -rf /root/ejbcadb.old
/bin/rm /opt/jboss-eap-6.4.0/ejbcadb*
/bin/rm /opt/jboss-eap-6.4.0/standalone/configuration/keystore/*
/bin/rm /tmp/jboss-cli.log
/bin/rm /tmp/ant-*.log
/bin/rm /opt/ejbca_ce_6_3_1_1/p12/*
find /opt/jboss-eap-6.4.0/standalone/log/ -type f -exec shred -u {} \;
find /opt/jboss-eap-6.4.0/standalone/configuration/standalone_xml_history/ -type f -exec shred -u {} \;
/bin/rm -rf /opt/jboss-eap-6.4.0/standalone/configuration/standalone_xml_history/*

#
# Identity
#
sudo shred -u /root/.ssh/authorized_keys

# DESTRUCTIVE - NO MORE LOGGING IN
# sudo shred -u /etc/ssh/*_key /etc/ssh/*_key.pub
# sudo shred /home/ec2-user/.ssh/authorized_keys

updatedb
shred -u ~/.*history
history -c

