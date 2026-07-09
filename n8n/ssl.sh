#!/bin/bash

set -e

mkdir ./certs; cd ./certs

tee n8n-csr.conf<<EOF
[ req ]
default_bits = 4096
prompt = no
default_md = sha384
req_extensions = req_ext
distinguished_name = dn

[ dn ]
C = US
ST = CO
L = a53
O = .
OU = .
CN = n8n.io

[ req_ext ]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = critical, serverAuth

[ alt_names ]
DNS.1 = *n8n
DNS.2 = n8n.io
EOF

#generate CA, server certificate and key

openssl genrsa -out n8n-ca.key.pem 4096

openssl req -new -x509 -sha256 -days 730 -key n8n-ca.key.pem \
-subj "/C=US/ST=CO/L=a53/O=./CN=n8n CA" -out n8n-ca.crt.pem

openssl genrsa -out n8n.key.pem 4096

openssl req -new -key n8n.key.pem -out n8n.csr -config n8n-csr.conf

openssl x509 -req -in n8n.csr -CA n8n-ca.crt.pem -CAkey n8n-ca.key.pem \
-CAcreateserial -out n8n.crt.pem -sha256 -days 365 \
-extfile n8n-csr.conf

chmod 640 *.pem
rm -f *.ext
rm -f *.tmp
rm -f *.conf
rm -f *.srl