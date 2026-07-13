#!/usr/bin/env bash
# Generate a self-signed CA + node keystore/truststore (JKS) for Cassandra
# node-to-node and client encryption. Produces cassandra.keystore.jks +
# cassandra.truststore.jks. Wire them via server_encryption_options /
# client_encryption_options (see README). Replace with CA-issued certs in prod.
#   ./tls/gen_cassandra_tls.sh [output_dir] [password]
set -euo pipefail
OUT="${1:-$(dirname "$0")}"; PW="${2:-cassandra-tls-pass}"; mkdir -p "$OUT"; cd "$OUT"
command -v keytool >/dev/null || { echo "keytool not found (install a JDK)"; exit 1; }
command -v openssl >/dev/null || { echo "openssl not found"; exit 1; }
rm -f ca.key ca.crt cassandra.keystore.jks cassandra.truststore.jks cert-file cert-signed
openssl req -new -x509 -keyout ca.key -out ca.crt -days 825 -nodes -subj "/CN=cassandra-ca"
keytool -genkeypair -alias cassandra -keyalg RSA -keysize 2048 -validity 825 \
  -keystore cassandra.keystore.jks -storepass "$PW" -keypass "$PW" -dname "CN=cassandra" \
  -ext "SAN=dns:cassandra,dns:cassandra1,dns:cassandra2,dns:cassandra3,dns:localhost,ip:127.0.0.1"
keytool -certreq -alias cassandra -keystore cassandra.keystore.jks -storepass "$PW" -file cert-file
openssl x509 -req -CA ca.crt -CAkey ca.key -in cert-file -out cert-signed -days 825 -CAcreateserial
keytool -importcert -alias CARoot -file ca.crt -keystore cassandra.keystore.jks -storepass "$PW" -noprompt
keytool -importcert -alias cassandra -file cert-signed -keystore cassandra.keystore.jks -storepass "$PW" -noprompt
keytool -importcert -alias CARoot -file ca.crt -keystore cassandra.truststore.jks -storepass "$PW" -noprompt
rm -f cert-file cert-signed ca.srl; chmod 644 cassandra.keystore.jks cassandra.truststore.jks
echo "wrote $OUT/cassandra.keystore.jks and $OUT/cassandra.truststore.jks (password: $PW)"
