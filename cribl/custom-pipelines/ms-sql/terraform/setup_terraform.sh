#!/bin/bash

INI_FILE="../config/config.ini"
LOG_FILE="terraform_config.log"

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
SQL_HOST=$(parse_ini "sql" "host")
SQL_PORT=$(parse_ini "sql" "port")
SQL_DB=$(parse_ini "sql" "db")
SQL_USER=$(parse_ini "sql" "user")
SQL_PASS=$(parse_ini "sql" "pass")
QUERIES_DIR=$(parse_ini "sql" "queries_dir")
PIPELINE_ID=$(parse_ini "sql" "pipeline_id" || echo "my_pipeline")
PIPELINE_GROUP=$(parse_ini "sql" "pipeline_group" || echo "local")
SOURCE_TAG=$(parse_ini "sql" "source_tag" || echo "mssql_db")
AGG_INTERVAL=$(parse_ini "sql" "aggregate_interval" || echo "1m")
SAMPLE_RATE=$(parse_ini "sql" "sample_rate" || echo 0.5)
LIMIT_EVENTS=$(parse_ini "sql" "limit_max_events" || echo 100000)
ERROR_OUTPUT=$(parse_ini "sql" "error_output" || echo "error_destination")
MAIN_OUTPUT=$(parse_ini "sql" "main_output" || echo "main_destination")
PIPELINE_VARIANT=$(parse_ini "sql" "pipeline_variant" || echo "logs")

if [ -z "$CRIBL_HOST" ] || [ -z "$CRIBL_USER" ] || [ -z "$CRIBL_PASS" ]; then
  log "ERROR" "Missing [cribl] keys"
  exit 1
fi

log "INFO" "Loaded config: CRIBL_HOST=$CRIBL_HOST, CRIBL_USER=$CRIBL_USER, CRIBL_PASS=****"

export TF_VAR_cribl_username="$CRIBL_USER"
export TF_VAR_cribl_password="$CRIBL_PASS"
export TF_VAR_sql_host="$SQL_HOST"
export TF_VAR_sql_port="$SQL_PORT"
export TF_VAR_sql_db="$SQL_DB"
export TF_VAR_sql_user="$SQL_USER"
export TF_VAR_sql_pass="$SQL_PASS"
export TF_VAR_queries_dir="$QUERIES_DIR"
export TF_VAR_pipeline_id="$PIPELINE_ID"
export TF_VAR_pipeline_group="$PIPELINE_GROUP"
export TF_VAR_source_tag="$SOURCE_TAG"
export TF_VAR_aggregate_interval="$AGG_INTERVAL"
export TF_VAR_sample_rate="$SAMPLE_RATE"
export TF_VAR_limit_max_events="$LIMIT_EVENTS"
export TF_VAR_error_output="$ERROR_OUTPUT"
export TF_VAR_main_output="$MAIN_OUTPUT"
export TF_VAR_pipeline_variant="$PIPELINE_VARIANT"

terraform init
terraform validate || { log "ERROR" "Terraform validation failed"; exit 1; }
terraform apply -auto-approve || { log "ERROR" "Terraform apply failed"; exit 1; }

log "INFO" "Terraform setup complete"