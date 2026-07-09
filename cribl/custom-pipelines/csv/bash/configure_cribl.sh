#!/bin/bash

INI_FILE="../config/config.ini"
LOG_FILE="cribl_config.log"
JSON_FILE="../config/pipeline_config.json"
MAX_RETRIES=5
BACKOFF=2

log() {
  local level="$1"
  shift
  echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $*" | tee -a "$LOG_FILE"
}

parse_ini() {
  local section="$1" key="$2"
  awk -F "=" '/^\['"$section"'\]/{a=1;next}/^\[/{a=0} a && $1=="'"$key"'" {gsub(/ /,"",$2); print $2}' "$INI_FILE"
}

if [ ! -f "$INI_FILE" ]; then
  log "ERROR" "INI file $INI_FILE not found"
  exit 1
fi

CRIBL_HOST=$(parse_ini "cribl" "host")
CRIBL_USER=$(parse_ini "cribl" "user")
CRIBL_PASS=$(parse_ini "cribl" "pass")
CSV_DIR=$(parse_ini "csv" "dir")
FILE_FILTER=$(parse_ini "csv" "file_filter" || echo "*.csv")
DELIMITER=$(parse_ini "csv" "delimiter" || echo ",")
HAS_HEADER=$(parse_ini "csv" "has_header" || echo true)
TRACKING_FIELD=$(parse_ini "csv" "tracking_field" || echo "modtime")
PIPELINE_ID=$(parse_ini "csv" "pipeline_id" || echo "my_csv_pipeline")
PIPELINE_GROUP=$(parse_ini "csv" "pipeline_group" || echo "local")
SOURCE_TAG=$(parse_ini "csv" "source_tag" || echo "csv_files")
AGG_INTERVAL=$(parse_ini "csv" "aggregate_interval" || echo "1m")
SAMPLE_RATE=$(parse_ini "csv" "sample_rate" || echo 0.5)
LIMIT_EVENTS=$(parse_ini "csv" "limit_max_events" || echo 100000)
ERROR_OUTPUT=$(parse_ini "csv" "error_output" || echo "error_destination")
MAIN_OUTPUT=$(parse_ini "csv" "main_output" || echo "main_destination")
PIPELINE_VARIANT=$(parse_ini "csv" "pipeline_variant" || echo "logs")

if [ -z "$CRIBL_HOST" ] || [ -z "$CRIBL_USER" ] || [ -z "$CRIBL_PASS" ]; then
  log "ERROR" "Missing [cribl] keys"
  exit 1
fi

log "INFO" "Loaded: CRIBL_HOST=$CRIBL_HOST, USER=$CRIBL_USER, PASS=****"
log "INFO" "Loaded: CSV_DIR=$CSV_DIR, FILE_FILTER=$FILE_FILTER, DELIMITER=$DELIMITER, HAS_HEADER=$HAS_HEADER, TRACKING_FIELD=$TRACKING_FIELD"
log "INFO" "Loaded: PIPELINE_ID=$PIPELINE_ID, GROUP=$PIPELINE_GROUP"
log "INFO" "Loaded: SOURCE_TAG=$SOURCE_TAG, AGG_INTERVAL=$AGG_INTERVAL, SAMPLE_RATE=$SAMPLE_RATE, LIMIT_EVENTS=$LIMIT_EVENTS"
log "INFO" "Loaded: ERROR_OUTPUT=$ERROR_OUTPUT, MAIN_OUTPUT=$MAIN_OUTPUT"
log "INFO" "Loaded: PIPELINE_VARIANT=$PIPELINE_VARIANT"

AUTH_HEADER="Authorization: Basic $(echo -n $CRIBL_USER:$CRIBL_PASS | base64)"

api_call() {
  # ... (same as previous)
}

PIPELINE_ENDPOINT="m/$PIPELINE_GROUP/pipelines"
log "INFO" "Checking/creating pipeline $PIPELINE_ID"
PIPELINE_ID_VARIANT="$PIPELINE_ID_$PIPELINE_VARIANT"
api_call "GET" "$PIPELINE_ENDPOINT/$PIPELINE_ID_VARIANT" "" "check_only"
if [ $? -eq 0 ]; then
  log "INFO" "Pipeline exists. Skipping creation."
else
  cp "$JSON_FILE" temp.json
  sed -i "s/{{pipeline_id}}/$PIPELINE_ID_VARIANT/g" temp.json
  sed -i "s/{{source_tag}}/$SOURCE_TAG/g" temp.json
  sed -i "s/{{aggregate_interval}}/$AGG_INTERVAL/g" temp.json
  sed -i "s/{{sample_rate}}/$SAMPLE_RATE/g" temp.json
  sed -i "s/{{limit_max_events}}/$LIMIT_EVENTS/g" temp.json
  sed -i "s/{{error_output}}/$ERROR_OUTPUT/g" temp.json
  sed -i "s/{{main_output}}/$MAIN_OUTPUT/g" temp.json

  PIPELINE_PAYLOAD=$(cat temp.json)
  api_call "POST" "$PIPELINE_ENDPOINT" "$PIPELINE_PAYLOAD" || exit 1
  rm temp.json
fi

if [ ! -d "$CSV_DIR" ]; then
  log "ERROR" "CSV dir $CSV_DIR not found"
  exit 1
fi

log "INFO" "Creating file collector"
COLLECTOR_ID="csv_file_collector"
COLLECTOR_PAYLOAD='{
  "id": "'"$COLLECTOR_ID"'",
  "type": "file",
  "description": "File Collector for CSV files with incremental loads",
  "config": {
    "path": "'"$CSV_DIR"'",
    "fileFilter": "'"$FILE_FILTER"'",
    "schedule": "0 2 * * *",
    "stateEnabled": true,
    "trackingColumn": "'"$TRACKING_FIELD"'",
    "incrementalLoad": true,
    "batchSize": 5000,
    "pipelineId": "'"$PIPELINE_ID_VARIANT"'",
    "throttlingRate": "5 MB",
    "maxRetries": 3,
    "retryDelay": 10,
    "connectionTimeout": 30000,
    "requestTimeout": 60000,
    "addFields": {"query_type": "'"$PIPELINE_VARIANT"'"}
  }
}'
api_call "POST" "collectors" "$COLLECTOR_PAYLOAD" || exit 1

log "INFO" "Completed"