#!/usr/bin/env bash
#
##
## Creating S3 based AMI
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
# 4. create image (as root)
#   Creates disk image of the instance the command is started on (instance you want to create AMI from)
#   Image requires quite a lot of free space.
#
ec2-bundle-vol -k /tmp/cert/private-key.pem -c /tmp/cert/certificate.pem -u 112233445566 -r x86_64 \
  -e /tmp/cert,/mnt/build -d /mnt/build --partition gpt

#
# Reformat manifest
#
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
#   a)  create S3 bucket enigma-ami
#   b)  be sure the user you are going to use has a permissions to work with the bucket - S3, bucket, permissions.
#   c)  the user has in IAM S3 policy attached / S3FullAccess.
#
ec2-upload-bundle -b enigma-ami/ejbca/ejbcav1 -m /mnt/build/image.manifest.xml --region us-east-1 \
  -a your_access_key_id -s your_secret_access_key

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









