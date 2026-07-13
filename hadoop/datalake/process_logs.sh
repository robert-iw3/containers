#!/usr/bin/env bash
# Run the distributed multi-format log-processing job (Hadoop Streaming on YARN):
#   /datalake/raw/logs  --parse+aggregate-->  /datalake/curated/log_summary
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
RT="$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)"
NN="$($RT ps --format '{{.Names}}' | grep -E 'namenode' | head -1)"
[ -n "$NN" ] || { echo "namenode container not running"; exit 1; }

$RT exec "$NN" mkdir -p /tmp/jobs
for f in "$DIR"/jobs/*.py; do $RT cp "$f" "$NN":/tmp/jobs/; done
STREAM=$($RT exec "$NN" bash -c 'ls $HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-*.jar 2>/dev/null | head -1')
[ -n "$STREAM" ] || { echo "hadoop-streaming jar not found"; exit 1; }

$RT exec "$NN" hdfs dfs -rm -r -f /datalake/curated/log_summary >/dev/null 2>&1 || true
echo "=== submitting Hadoop Streaming job to YARN ==="
$RT exec "$NN" bash -c "hadoop jar $STREAM \
  -files /tmp/jobs/parse_logs_mapper.py,/tmp/jobs/count_reducer.py \
  -mapper 'python3 parse_logs_mapper.py' \
  -reducer 'python3 count_reducer.py' \
  -input /datalake/raw/logs -output /datalake/curated/log_summary"

echo "=== curated log summary (source::level -> count) ==="
$RT exec "$NN" hdfs dfs -cat '/datalake/curated/log_summary/part-*'
