#!/usr/bin/env bash
# Create Kafka topics declaratively from topics.yaml (idempotent, --if-not-exists).
# Runs inside the apache/kafka image (Alpine, awk -- no python), so the config is
# parsed with awk.
#
#   apply_topics.sh <bootstrap-server> <topics.yaml>
set -euo pipefail

BOOTSTRAP="${1:-localhost:9092}"
CONFIG="${2:-/topics.yaml}"
KT=/opt/kafka/bin/kafka-topics.sh

awk '
  /^[[:space:]]*-[[:space:]]*name:/ {
    if (name != "") print name "|" parts "|" rf "|" configs
    name=$0; sub(/.*name:[[:space:]]*/,"",name); parts="1"; rf="1"; configs=""; next
  }
  /^[[:space:]]*partitions:/         { v=$0; sub(/.*partitions:[[:space:]]*/,"",v);         parts=v;   next }
  /^[[:space:]]*replication_factor:/ { v=$0; sub(/.*replication_factor:[[:space:]]*/,"",v); rf=v;      next }
  /^[[:space:]]*configs:/            { v=$0; sub(/.*configs:[[:space:]]*/,"",v);            configs=v; next }
  END { if (name != "") print name "|" parts "|" rf "|" configs }
' "$CONFIG" | while IFS='|' read -r name parts rf configs; do
  cfgargs=()
  if [ -n "$configs" ]; then
    IFS=',' read -ra kvs <<< "$configs"
    for kv in "${kvs[@]}"; do cfgargs+=(--config "$kv"); done
  fi
  echo "topic: $name (partitions=$parts rf=$rf configs=[$configs])"
  "$KT" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
    --topic "$name" --partitions "$parts" --replication-factor "$rf" "${cfgargs[@]}"
done

echo "--- topics on the cluster ---"
"$KT" --bootstrap-server "$BOOTSTRAP" --list
