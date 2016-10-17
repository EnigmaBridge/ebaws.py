# Connections made during the PKI installation

* Python pip modules update
  * Connects to `pypi.python.org`
  * Fetches new version of Python modules related to the installation script.

* ec2-metadata call
  * Internally it connects to the host and performs REST calls such as GET `/latest/meta-data/instance-type/`
  * The following ec2-metadata is called: `ec2-metadata -a -i -t -z -v -p`
    * ami-id (required)
    * instance-id (required, fraud detection, continuity)
    * instance-type (client stats, support - e.g., size of RAM, recommendation on num. of certs)
    * placement (client stats, latency stats)
    * public-ipv4 (required)
    * public-hostname (required)

* Port test on 443
  * Testing whether port 443 is open for the LetsEncrypt domain verification
  * Script starts a simple TCP server on the `0.0.0.0:443`
  * It tries to connect to the `public-ipv4:443`

* EnigmaBridge new identity generation
  * Connects to `hut6.enigmabridge.com:8445`
  * Performs REST over HTTPS
    * Registering a new client `https://hut6.enigmabridge.com:8445/api/v1/client`. Client's email address and AMI details loaded with command above is submitted.
    * Asking for a new API key `https://hut6.enigmabridge.com:8445/api/v1/client`
    * Enrolling for a new domain in the EnigmaBridge Dynamic DNS `https://hut6.enigmabridge.com:8445/api/v1/apikey`
    * Get a new challenge for domain request `https://hut6.enigmabridge.com:8445/api/v1/apikey`
    * Refresh domain binding `https://hut6.enigmabridge.com:8445/api/v1/apikey`
  
* Generating a new RSA keys in the crypto token
  * TCP connection to EnigmaBridge procution servers `*.enigmabridge.com`, ports 11112, 11110
 
* LetsEncrypt certificate issuing for a new domains associated to the instance
  * Certbot classical operation - contacts LetsEncrypt CA, registers an account and asks for a domain verification. E.g. the LetsEncrypt API: `acme-v01.api.letsencrypt.org`
  * Certbot clients starts a local HTTPS server with SNI domain verification method. 
  * Letsencrypt CA/RA tries to connect to `public-ipv4:443` and check the certificate. E.g., `66.133.109.36` connects.
  * Once verified, certificate is downloaded
  
* Test if 8443 is reachable on the `public-ipv4`
  * Simple TCP connect to the `public-ipv4:8443` is made
  
  


