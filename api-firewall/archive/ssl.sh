#!/bin/bash
set -e

mkdir certs && cd certs

tee api-fw-csr.conf<<EOF
[ req ]
default_bits = 4096
prompt = no
default_md = sha512
req_extensions = req_ext
distinguished_name = dn

[ dn ]
C = US
ST = CO
L = range
O = testing
OU = wallarm
CN = api-fw

[ req_ext ]
subjectAltName = @alt_names
basicConstraints = CA:TRUE
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = critical, serverAuth, clientAuth

[ alt_names ]
DNS.1 = *api-fw
DNS.2 = localhost
EOF

#generate CA, server certificate and key
openssl genrsa -out ca.key.pem 4096

openssl req -new -x509 -days 730 -key ca.key.pem \
-subj "/C=US/ST=CO/L=a53/O=Testing/CN=api-fw SSL Root CA" -out ca.crt.pem

openssl req -new -key api-fw.key.pem -out api-fw.csr -config api-fw-csr.conf

openssl x509 -req -in api-fw.csr -CA ca.crt.pem -CAkey ca.key.pem \
-CAcreateserial -sha512 -out api-fw.crt.pem -days 365 \
-extfile elasticsearch-csr.conf

chmod 640 *.pem
rm -f *.ext
rm -f *.tmp
rm -f *.conf
rm -f *.srl