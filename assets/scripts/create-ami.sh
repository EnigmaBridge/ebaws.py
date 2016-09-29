#!/usr/bin/env bash
#
# http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-instance-store-ami.html
#
# 1. Create IAM access key - CSV will be downloaded
#
# 2. create X509 private key + self signed certificate, upload to IAM (manage signing certificates).
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
#  -  - create a new volume to fit the whole image
#  -  - attach the volume to the instance: /dev/xvdf1
#  -  - sudo fdisk /dev/xvdf create a new partition table (g), and a new primary partition (n)
#  -  - mkfs.ext4 /dev/xvdf1
#  -  - mount /dev/xvdf1 /mnt/build
#
# 4. create image (as root)
#   Image requires quite a lot of free space.
#
ec2-bundle-vol -k /tmp/cert/private-key.pem -c /tmp/cert/certificate.pem -u 112233445566 -r x86_64 -e /tmp/cert,/mnt/build -d /mnt/build --partition gpt

#
# 5. Upload to S3.
#   a)  create S3 bucket enigma-ami
#   b)  be sure the user you are going to use has a permissions to work with the bucket - S3, bucket, permissions.
#   c)  the user has in IAM S3 policy attached / S3FullAccess.
#
ec2-upload-bundle -b enigma-ami/ejbca/ejbcav1 -m /mnt/build/image.manifest.xml --region us-east-1 -a your_access_key_id -s your_secret_access_key











