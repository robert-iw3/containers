#!/usr/bin/env bash
# Generate the Flink SQL job from a pipeline config and submit it to the running
# session cluster.
#
#   ./pipelines/run_pipeline.sh [pipelines/pipeline_config.yaml]
set -euo pipefail

CONFIG="${1:-$(dirname "$0")/pipeline_config.yaml}"
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$DIR/pipeline.sql"

python3 "$DIR/build_pipeline.py" "$CONFIG" > "$OUT"
echo "generated $OUT from $CONFIG"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="podman-compose"
fi

# Submit the job by running sql-client inside the JobManager (the pipelines dir is
# mounted there). sql-client submits the streaming job to the cluster and returns;
# the job keeps running. Watch it in the UI at http://localhost:8081.
$COMPOSE -f "$DIR/../docker-compose.yml" exec -T jobmanager \
  /opt/flink/bin/sql-client.sh -f /opt/pipelines/pipeline.sql
