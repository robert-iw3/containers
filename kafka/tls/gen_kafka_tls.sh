#!/usr/bin/env bash
# Generate a self-signed CA + a broker keystore/truststore (JKS) for Kafka SSL.
# Produces kafka.keystore.jks + kafka.truststore.jks, used by the SSL listener in
# docker-compose.tls.yml. Replace with CA-issued certs for production.
#
#   ./tls/gen_kafka_tls.sh [output_dir] [password]
set -euo pipefail

OUT="${1:-$(dirname "$0")}"
PW="${2:-kafka-tls-pass}"
mkdir -p "$OUT"
cd "$OUT"
command -v keytool >/dev/null || { echo "keytool not found (install a JDK)"; exit 1; }
command -v openssl >/dev/null || { echo "openssl not found"; exit 1; }

rm -f ca.key ca.crt kafka.keystore.jks kafka.truststore.jks cert-file cert-signed

# 1. self-signed CA
openssl req -new -x509 -keyout ca.key -out ca.crt -days 825 -nodes -subj "/CN=kafka-ca"

# 2. broker keystore with a key whose SANs cover the broker DNS names
keytool -genkeypair -alias kafka -keyalg RSA -keysize 2048 -validity 825 \
  -keystore kafka.keystore.jks -storepass "$PW" -keypass "$PW" \
  -dname "CN=kafka" \
  -ext "SAN=dns:kafka1,dns:kafka2,dns:kafka3,dns:localhost,ip:127.0.0.1"

# 3. sign the broker cert with the CA
keytool -certreq -alias kafka -keystore kafka.keystore.jks -storepass "$PW" -file cert-file
openssl x509 -req -CA ca.crt -CAkey ca.key -in cert-file -out cert-signed -days 825 -CAcreateserial
keytool -importcert -alias CARoot -file ca.crt -keystore kafka.keystore.jks -storepass "$PW" -noprompt
keytool -importcert -alias kafka -file cert-signed -keystore kafka.keystore.jks -storepass "$PW" -noprompt

# 4. truststore trusts the CA
keytool -importcert -alias CARoot -file ca.crt -keystore kafka.truststore.jks -storepass "$PW" -noprompt

rm -f cert-file cert-signed ca.srl
chmod 644 kafka.keystore.jks kafka.truststore.jks
echo "wrote $OUT/kafka.keystore.jks and $OUT/kafka.truststore.jks (password: $PW)"
