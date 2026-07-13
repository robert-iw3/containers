#!/usr/bin/env bash
# Download the Flink SQL Kafka connector jar (Flink 2.x) into this directory.
set -euo pipefail
V="${1:-5.0.0-2.2}"
cd "$(dirname "$0")"
curl -fsSL -o flink-sql-connector-kafka.jar \
  "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${V}/flink-sql-connector-kafka-${V}.jar"
echo "downloaded flink-sql-connector-kafka ${V}"
