#!/bin/bash

set -e

mkdir ./certs; cd ./certs

tee elasticsearch-csr.conf<<EOF
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
OU = elastic
CN = elasticsearch

[ req_ext ]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = critical, serverAuth

[ alt_names ]
DNS.1 = *elasticsearch
DNS.2 = localhost
EOF

tee kibana-csr.conf<<EOF
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
OU = elastic
CN = kibana

[ req_ext ]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = critical, serverAuth

[ alt_names ]
DNS.1 = *kibana
DNS.2 = localhost
EOF

tee fleet-server-csr.conf<<EOF
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
OU = elastic
CN = fleet-server

[ req_ext ]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = critical, serverAuth

[ alt_names ]
DNS.1 = *fleet-server
DNS.2 = localhost
EOF

#generate CA, server certificate and key

openssl genrsa -out elastic-ca.key.pem 4096

openssl req -new -x509 -sha256 -days 730 -key elastic-ca.key.pem \
-subj "/C=US/ST=CO/L=testing/O=elastic/CN=elastic CA" -out elastic-ca.crt.pem

openssl genrsa -out elasticsearch.key.pem.tmp 4096
openssl genrsa -out kibana.key.pem.tmp 4096
openssl genrsa -out fleet-server.key.pem.tmp 4096

openssl pkcs8 -inform PEM -outform PEM -in elasticsearch.key.pem.tmp -topk8 -nocrypt -v1 PBE-SHA1-3DES -out elasticsearch.key.pem
openssl pkcs8 -inform PEM -outform PEM -in kibana.key.pem.tmp -topk8 -nocrypt -v1 PBE-SHA1-3DES -out kibana.key.pem
openssl pkcs8 -inform PEM -outform PEM -in fleet-server.key.pem.tmp -topk8 -nocrypt -v1 PBE-SHA1-3DES -out fleet-server.key.pem

openssl req -new -key elasticsearch.key.pem -out elasticsearch.csr -config elasticsearch-csr.conf
openssl req -new -key kibana.key.pem -out kibana.csr -config kibana-csr.conf
openssl req -new -key fleet-server.key.pem -out fleet-server.csr -config fleet-server-csr.conf

openssl x509 -req -in elasticsearch.csr -CA elastic-ca.crt.pem -CAkey elastic-ca.key.pem \
-CAcreateserial -sha256 -out elasticsearch.crt.pem -days 365 \
-extfile elasticsearch-csr.conf

openssl x509 -req -in kibana.csr -CA elastic-ca.crt.pem -CAkey elastic-ca.key.pem \
-CAcreateserial -sha256 -out kibana.crt.pem -days 365 \
-extfile kibana-csr.conf

openssl x509 -req -in fleet-server.csr -CA elastic-ca.crt.pem -CAkey elastic-ca.key.pem \
-CAcreateserial -sha256 -out fleet-server.crt.pem -days 365 \
-extfile fleet-server-csr.conf

chmod 640 *.pem
rm -f *.ext
rm -f *.tmp
rm -f *.conf
rm -f *.srl