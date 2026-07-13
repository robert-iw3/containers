#!/usr/bin/env bash
# Create the HDFS datalake zones and load the multi-format sample logs.
#   raw/ (landing) -> curated/ (processed) -> warehouse/ (serving)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
RT="$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)"
NN="$($RT ps --format '{{.Names}}' | grep -E 'namenode' | head -1)"
[ -n "$NN" ] || { echo "namenode container not running"; exit 1; }
echo "namenode: $NN"

$RT exec "$NN" hdfs dfsadmin -safemode wait >/dev/null 2>&1 || true
$RT exec "$NN" hdfs dfs -mkdir -p /datalake/raw/logs /datalake/curated /datalake/warehouse
$RT exec "$NN" mkdir -p /tmp/sample_logs
for f in "$DIR"/sample_logs/*.log; do $RT cp "$f" "$NN":/tmp/sample_logs/; done
$RT exec "$NN" bash -c 'hdfs dfs -put -f /tmp/sample_logs/*.log /datalake/raw/logs/'

echo "=== datalake layout ==="
$RT exec "$NN" hdfs dfs -ls -R /datalake
echo "=== replication of a raw file (should be 3) ==="
$RT exec "$NN" bash -c 'hdfs dfs -stat "%r" /datalake/raw/logs/app.json.log'
