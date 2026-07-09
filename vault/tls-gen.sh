#!/bin/bash

# Modify attributes in "vault-csr.conf" to your environment

set -e

mkdir /certs; cd /certs

tee vault-csr.conf<<EOF
[ req ]
default_bits = 4096
prompt = no
default_md = sha384
req_extensions = req_ext
distinguished_name = dn

[ dn ]
C = US
ST = CO
L = range
O = testing
OU = vault
CN = vault

[ req_ext ]
subjectAltName = @alt_names
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = critical, serverAuth

[ alt_names ]
DNS.1 = *vault
DNS.2 = localhost
EOF

#generate CA, server certificate and key

openssl genrsa -out vault-ca.key.pem 4096

openssl req -new -x509 -sha256 -days 730 -key vault-ca.key.pem \
-subj "/C=US/ST=CO/L=testing/O=vault/CN=vault CA" -out vault-ca.crt.pem

openssl genrsa -out vault.key.pem 4096

openssl req -new -key vault.key.pem -out vault.csr -config vault-csr.conf

openssl x509 -req -in vault.csr -CA vault-ca.crt.pem -CAkey vault-ca.key.pem \
-CAcreateserial -sha256 -out vault.crt.pem -days 365 \
-extfile vault-csr.conf

chmod 640 *.pem
rm -f *.ext
rm -f *.tmp
rm -f *.conf
rm -f *.srl