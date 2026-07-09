#!/bin/bash

set -e

mkdir ./certs; cd ./certs

tee redmine-csr.conf<<EOF
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
CN = redmine.io

[ req_ext ]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = critical, serverAuth

[ alt_names ]
DNS.1 = *redmine
DNS.2 = redmine.io
EOF

#generate CA, server certificate and key

openssl genrsa -out redmine-ca.key.pem 4096

openssl req -new -x509 -sha256 -days 730 -key redmine-ca.key.pem \
-subj "/C=US/ST=CO/L=a53/O=./CN=redmine CA" -out redmine-ca.crt.pem

openssl genrsa -out redmine.key.pem 4096

openssl req -new -key redmine.key.pem -out redmine.csr -config redmine-csr.conf

openssl x509 -req -in redmine.csr -CA redmine-ca.crt.pem -CAkey redmine-ca.key.pem \
-CAcreateserial -out redmine.crt.pem -sha256 -days 365 \
-extfile redmine-csr.conf

chmod 640 *.pem
rm -f *.ext
rm -f *.tmp
rm -f *.conf
rm -f *.srl