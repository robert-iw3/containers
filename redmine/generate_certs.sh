#!/bin/bash

# Exit on error
set -e

# Directory for certificates
CERT_DIR="certs"
CA_CNF="$CERT_DIR/ca.cnf"
SERVER_CNF="$CERT_DIR/server.cnf"
DAYS_VALID=365
KEY_SIZE=2048

# Create certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Generate CA configuration
cat > "$CA_CNF" << EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no
default_bits = $KEY_SIZE

[req_distinguished_name]
C = US
ST = Colorado
L = Denver
O = Redmine
OU = IT
CN = Redmine CA

[v3_ca]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical, CA:true
keyUsage = critical, cRLSign, keyCertSign
EOF

# Generate server CSR configuration
cat > "$SERVER_CNF" << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no
default_bits = $KEY_SIZE

[req_distinguished_name]
C = US
ST = Colorado
L = Denver
O = Redmine
OU = IT
CN = redmine.io

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = redmine.io
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

# Generate CA key and certificate
openssl genrsa -out "$CERT_DIR/ca.key" $KEY_SIZE
openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" -sha256 -days $DAYS_VALID -out "$CERT_DIR/ca.crt" -config "$CA_CNF"

# Generate server key and CSR
openssl genrsa -out "$CERT_DIR/redmine.key" $KEY_SIZE
openssl req -new -key "$CERT_DIR/redmine.key" -out "$CERT_DIR/redmine.csr" -config "$SERVER_CNF"

# Sign server certificate with CA
openssl x509 -req -in "$CERT_DIR/redmine.csr" -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/redmine.crt" -days $DAYS_VALID -sha256 -extensions v3_req -extfile "$SERVER_CNF"

# Generate DH parameters
openssl dhparam -out "$CERT_DIR/dhparam.pem" $KEY_SIZE

# Set permissions
chmod 600 "$CERT_DIR/redmine.key" "$CERT_DIR/ca.key"
chmod 644 "$CERT_DIR/redmine.crt" "$CERT_DIR/ca.crt" "$CERT_DIR/dhparam.pem"

# Clean up
rm -f "$CERT_DIR/redmine.csr" "$CERT_DIR/ca.srl"

echo "Certificates generated successfully in $CERT_DIR:"
ls -l "$CERT_DIR"