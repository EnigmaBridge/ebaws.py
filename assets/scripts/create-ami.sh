#!/usr/bin/env bash
#
##
## Creating S3 based AMI, EBS based AMI (EBS is below)
##
# http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-instance-store-ami.html
# https://robpickering.com/2010/07/create-a-full-backup-image-of-your-amazon-ec2-instance-2-129
#
# 1. Create IAM access key for the user (Access Key ID, Secret Key), required for S3 upload
#
# 2. Create RSA-2048 private key + X509 self signed certificate, upload to IAM (manage signing certificates).
#    http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/set-up-ami-tools.html#ami-tools-managing-certs
#
#    openssl genrsa 2048 > private-key.pem
#    openssl req -new -x509 -nodes -sha256 -days 365 -key private-key.pem -outform PEM -out certificate.pem#
#
#    For cloudwatch, etc: PKCS8 (not needed for our case)
#    openssl pkcs8 -topk8 -nocrypt -inform PEM -in private-key.pem -out private-key-8.pem
#
# 3. scp the private key and certificate to the instance under /tmp/cert
#
#  - Optionally, if you dont have 2x $USED_SPACE of the free space on your /tmp:
#  -  - create a new volume in the EC2 Web Console to fit the whole image
#  -  - attach the volume to the instance, to /dev/xvdf1
#  -  - sudo fdisk /dev/xvdf create a new partition table (g), and a new primary partition (n)
#  -  - mkfs.ext4 /dev/xvdf1
#  -  - mount /dev/xvdf1 /mnt/build
#

#
# Export data
#
export AWS_ACC=112233445566
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
export AMI_REGION=eu-west-1
export INSTANCE_ID=ec2-metadata -i | cut -d ' ' -f 2
export AMI_ID=`ec2-metadata -a | cut -d ' ' -f 2`

# 4. create image (as root)
#   Creates disk image of the instance the command is started on (instance you want to create AMI from)
#   Image requires quite a lot of free space.
#   Size 8192 MB corresponds to the size of a new created volume with 8GiB
#
ec2-bundle-vol -k /tmp/cert/private-key.pem -c /tmp/cert/certificate.pem -u $AWS_ACC -r x86_64 \
  -e /tmp/cert,/mnt/build,/var/swap.1 -d /mnt/build --partition gpt --size 8192

#
# If you want only EBS-backed AMI you can skip to EBS-backed AMI description
# You can even CTRL+C volume creation once image file is completed (skip encryption, manifest creation).
#

# For S3 you will probably need to change the manifest:
# At first, reformat manifest
sudo cp /mnt/build/image.manifest.xml /mnt/build/image.manifest.xml.bak
sudo xmllint --format /mnt/build/image.manifest.xml.bak | sudo tee /mnt/build/image.manifest.xml

#
# Fix block_device_mapping
#  - here you can add new storage devices to the AMI
#  - fix the block mapping - xvda is not accepted by aws ec2 register-image
#    <block_device_mapping>
#      <mapping>
#        <virtual>ami</virtual>
#        <device>sda</device>
#      </mapping>
#      <mapping>
#        <virtual>root</virtual>
#        <device>/dev/sda1</device>
#      </mapping>
#    </block_device_mapping>

#
# 5. Upload to S3.
#   S3 uploading requirements:
#     a) create S3 bucket enigma-ami
#     b) be sure the user you are going to use has a permissions to work with the bucket - S3, bucket, permissions.
#     c) the user has in IAM S3 policy attached / S3FullAccess.
#
ec2-upload-bundle -b enigma-ami/ejbca/ejbcav1 -m /mnt/build/image.manifest.xml --region us-east-1 \
  -a $AWS_ACCESS_KEY_ID -s $AWS_SECRET_ACCESS_KEY

#
# 6. Register AMI
#   This can be done also from your local PC.
#   If you don't have aws:
#      pip install --upgrade awscli
#      pip install --upgrade --user awscli (for Mac users)
#        For Mac aws is located: /Library/Python/2.7/bin/aws
#
aws ec2 register-image --image-location enigma-ami/ejbca/ejbcav1/image.manifest.xml --name 'EnigmaBridge-EJBCA' \
  --virtualization-type hvm --region us-east-1 \
  --description 'EnigmaBridge integrated EJBCA AMI'

#
# ----------------------------------------------------------------------------------------------------------------------
#

#
# Conversion to EBS-backed AMI
# http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_ConvertingS3toEBS.html

#
# Prepare an Amazon EBS volume for your new AMI.
# Check out the size of the created image, has to be at least that large
#
aws ec2 create-volume --size 8 --region $AMI_REGION --availability-zone ${AMI_REGION}a --volume-type gp2

export VOLUME_ID=vol-xx1122

# Attach the volume to the AMI
aws ec2 attach-volume --volume-id $VOLUME_ID --instance-id $INSTANCE_ID --device /dev/sdb --region $AMI_REGION

# DD-bundle to the new volume
#   We can skip ec2-download-bundle, ec2-unbundle as we have the unbundled image ready
#   If desired, use kill -USR1 DDPID to monitor DDs progress
sudo dd if=/mnt/build/image of=/dev/sdb bs=1M

# Remove unwanted fstab entries (e.g., file swaps)
# Remove SSH keys
sudo partprobe /dev/sdb
lsblk
sudo mkdir -p /mnt/ebs
sudo mount /dev/sdb1 /mnt/ebs
sudo vim /mnt/ebs/etc/fstab
sudo find /mnt/ebs/etc/ssh/ -name '*key*' -exec shred -u -z {} \;
sudo umount /mnt/ebs

# Zeroize free space
zerofree -v /dev/sdb1

# Detach EBS
aws ec2 detach-volume --volume-id $VOLUME_ID --region $AMI_REGION

# Create AMI
aws ec2 create-snapshot --region $AMI_REGION --description "EnigmaBridge-EJBCA" --volume-id $VOLUME_ID
export SNAPSHOT_ID=snap-xx112233

# Verify snapshot - wait until the progress is 100%
aws ec2 describe-snapshots --region $AMI_REGION --snapshot-id $SNAPSHOT_ID

# Get Current AMI data - architecture, kernel id (if applicable), ramdisk id (if applicable)
aws ec2 describe-images --region $AMI_REGION --image-id $AMI_ID --output text

# Create new AMI
aws ec2 register-image --region $AMI_REGION --name 'EnigmaBridge-EJBCA' \
  --block-device-mappings DeviceName=/dev/xvda,Ebs={SnapshotId=${SNAPSHOT_ID}} \
  --description 'EnigmaBridge integrated EJBCA AMI' \
  --virtualization-type hvm --architecture x86_64 \
  --root-device-name /dev/xvda

# Delete the EBS volume
aws ec2 delete-volume --volume-id $VOLUME_ID






