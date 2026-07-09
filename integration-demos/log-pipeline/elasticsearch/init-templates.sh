#!/bin/sh
set -eu

ES_URL="${ES_URL:-http://elasticsearch:9200}"

until curl -sf "${ES_URL}/_cluster/health" > /dev/null; do
  sleep 2
done

curl -sf -X PUT "${ES_URL}/_index_template/logs-raw-template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["logs-raw*"],
    "template": {
      "settings": {"number_of_shards": 1, "number_of_replicas": 0},
      "mappings": {
        "properties": {
          "timestamp": {"type": "date"},
          "trace_id": {"type": "keyword"},
          "service": {"type": "keyword"},
          "host": {"type": "keyword"},
          "level": {"type": "keyword"},
          "message": {"type": "text"},
          "status_code": {"type": "integer"},
          "duration_ms": {"type": "double"}
        }
      }
    }
  }'

curl -sf -X PUT "${ES_URL}/_index_template/logs-metrics-template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["logs-metrics-1m*"],
    "template": {
      "settings": {"number_of_shards": 1, "number_of_replicas": 0},
      "mappings": {
        "properties": {
          "window_start": {"type": "date"},
          "window_end": {"type": "date"},
          "service": {"type": "keyword"},
          "level": {"type": "keyword"},
          "event_count": {"type": "long"},
          "avg_duration_ms": {"type": "double"},
          "error_count": {"type": "long"},
          "distinct_hosts": {"type": "long"}
        }
      }
    }
  }'

curl -sf -X PUT "${ES_URL}/_index_template/logs-daily-summary-template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["logs-daily-summary*"],
    "template": {
      "settings": {"number_of_shards": 1, "number_of_replicas": 0},
      "mappings": {
        "properties": {
          "date": {"type": "date", "format": "yyyy-MM-dd"},
          "total_events": {"type": "long"},
          "total_errors": {"type": "long"},
          "error_rate": {"type": "double"},
          "generated_at": {"type": "date"},
          "services": {
            "type": "nested",
            "properties": {
              "service": {"type": "keyword"},
              "event_count": {"type": "long"},
              "error_count": {"type": "long"},
              "avg_duration_ms": {"type": "double"}
            }
          }
        }
      }
    }
  }'

echo "index templates installed"
