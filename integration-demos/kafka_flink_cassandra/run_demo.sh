#!/usr/bin/env bash
# End-to-end big-data pipeline: producer -> Kafka -> Flink -> Kafka -> Cassandra.
# Reuses the kafka producer, the flink SQL generator, and the cassandra schema from
# their respective directories.
#
#   ./run_demo.sh [scenario]      # scenario: telemetry (default) | orders
set -euo pipefail

SCENARIO="${1:-telemetry}"
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$DIR/../.."                      # containers/
JOB="$DIR/flink_jobs/${SCENARIO}_to_cassandra.yaml"
[ -f "$JOB" ] || { echo "no job config for scenario '$SCENARIO' ($JOB)"; exit 1; }

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"; RT=docker
else
  COMPOSE="podman-compose"; RT=podman
fi
cd "$DIR"

echo "==> 1/6 bring up the cluster (kafka, cassandra, flink)"
$COMPOSE up -d kafka1 cassandra jobmanager taskmanager

echo "==> 2/6 wait for kafka + flink + cassandra"
until $RT exec "$($RT ps -qf name=cassandra | head -1)" nodetool status 2>/dev/null | grep -q '^UN'; do sleep 5; done
until curl -fsS http://localhost:8081/overview >/dev/null 2>&1; do sleep 5; done

KAFKA=$($RT ps --format '{{.Names}}' | grep -E 'kafka1' | head -1)
CASS=$($RT ps --format '{{.Names}}' | grep -E '_cassandra' | head -1)
JM=$($RT ps --format '{{.Names}}' | grep -E 'jobmanager' | head -1)

echo "==> 3/6 create Kafka topics + apply Cassandra schema"
for t in iot-metrics sensor-rollups pizza-orders order-rollups; do
  $RT exec "$KAFKA" /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka1:9092 \
    --create --if-not-exists --topic "$t" --partitions 4 --replication-factor 1 >/dev/null 2>&1 || true
done
$RT cp "$REPO/cassandra/schema/schema.cql" "$CASS":/tmp/schema.cql
$RT exec "$CASS" cqlsh -f /tmp/schema.cql
$RT cp "$DIR/flink_jobs/demo_schema.cql" "$CASS":/tmp/demo_schema.cql 2>/dev/null && \
  $RT exec "$CASS" cqlsh -f /tmp/demo_schema.cql || true

echo "==> 4/6 generate + submit the Flink SQL job (scenario: $SCENARIO)"
python3 "$REPO/flink/pipelines/build_pipeline.py" "$JOB" > "$DIR/flink_jobs/${SCENARIO}.sql"
$RT exec "$JM" /opt/flink/bin/sql-client.sh -f "/opt/jobs/${SCENARIO}.sql" 2>&1 | grep -iE "job id" || true

echo "==> 5/6 start the producer (Ctrl-C to stop) and the Cassandra sink"
echo "    producer: kafka/producers/produce.py --scenario $SCENARIO"
echo "    sink:     sinks/cassandra_sink.py"
$COMPOSE --profile tools up -d cassandra-sink
$COMPOSE run --rm producer python3 /producers/produce.py --scenario "$SCENARIO" \
  --bootstrap kafka1:9092 --rate 3000 --count 200000 || true

echo "==> 6/6 done. Query the results:"
echo "    $RT exec $CASS cqlsh -e \"SELECT * FROM telemetry.sensor_rollups LIMIT 10;\""
