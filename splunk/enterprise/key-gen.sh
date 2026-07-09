#!/bin/sh

if ! (set -o pipefail 2>/dev/null); then
  # dash does not support pipefail
  set -efx
else
  set -efx -o pipefail
fi

SPLUNK_HOME="/opt/splunk"
mkdir -p $SPLUNK_HOME/etc/auth/mycerts

SPLUNK_USER="splunk"
if ! id -u "$SPLUNK_USER" >/dev/null 2>&1; then
  echo "\"$SPLUNK_USER\" user not found, creating..."
  useradd --system --create-home --home-dir "$SPLUNK_HOME" --shell "/usr/sbin/nologin" "$SPLUNK_USER"
else
  echo "\"$SPLUNK_USER\" user exists"
fi

${SPLUNK_HOME}/bin/splunk cmd \
    openssl genpkey -aes-256-cbc -algorithm RSA -out myServerPrivateKey.key -pkeyopt rsa_keygen_bits:2048

${SPLUNK_HOME}/bin/splunk cmd \
    openssl req -new -key myCertAuthPrivateKey.key -out myCertAuthCertificate.csr -config splunk-cert_openssl.conf

${SPLUNK_HOME}/bin/splunk cmd \
    openssl x509 -req -in myCertAuthCertificate.csr -sha512 -signkey myCertAuthPrivateKey.key -CAcreateserial -out myCertAuthCertificate.pem -days 1095

${SPLUNK_HOME}/bin/splunk cmd \
    openssl genrsa -aes256 -out myServerPrivateKey.key 2048

${SPLUNK_HOME}/bin/splunk cmd \
    openssl req -new -key myServerPrivateKey.key -out myServerCertificate.csr

${SPLUNK_HOME}/bin/splunk cmd \
    openssl x509 -req -in myServerCertificate.csr -SHA256 -CA myCertAuthCertificate.pem -CAkey myCertAuthPrivateKey.key -CAcreateserial -out myServerCertificate.pem -days 1095