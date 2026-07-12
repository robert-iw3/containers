#!/usr/bin/env bash
# Generate the JKS keystore + truststore Flink uses for SSL:
#   * internal SSL  (JobManager <-> TaskManager RPC/data, mutual auth)
#   * REST SSL      (the UI / REST API)
# One self-signed cert shared cluster-wide (SANs cover the compose/k8s service names
# and localhost). Replace with a CA-issued cert for production.
#
#   ./tls/gen_flink_tls.sh [output_dir] [password]
set -euo pipefail

OUT="${1:-$(dirname "$0")}"
PW="${2:-flink-tls-pass}"
mkdir -p "$OUT"

command -v keytool >/dev/null || { echo "keytool not found (install a JDK)"; exit 1; }

rm -f "$OUT/keystore.jks" "$OUT/truststore.jks" "$OUT/flink.cer"

keytool -genkeypair -alias flink -keyalg RSA -keysize 2048 -validity 825 \
  -keystore "$OUT/keystore.jks" -storepass "$PW" -keypass "$PW" \
  -dname "CN=flink" \
  -ext "SAN=dns:jobmanager,dns:flink-jobmanager,dns:flink-jobmanager.flink.svc.cluster.local,dns:localhost,ip:127.0.0.1"

keytool -exportcert -alias flink -keystore "$OUT/keystore.jks" -storepass "$PW" -rfc -file "$OUT/flink.cer"
keytool -importcert -noprompt -alias flink -file "$OUT/flink.cer" \
  -keystore "$OUT/truststore.jks" -storepass "$PW"

rm -f "$OUT/flink.cer"
# World-readable so the in-container flink user (uid 9999) can read the mounted files.
chmod 644 "$OUT/keystore.jks" "$OUT/truststore.jks"
echo "wrote $OUT/keystore.jks and $OUT/truststore.jks (password: $PW)"
