# Provision the MS-SQL pipeline + database collector on a Cribl leader via
# its REST API (same endpoints as the bash/ and python/ methods). Uses only
# the null provider; no Cribl-specific terraform provider is required.
# The database collector references a pre-created database connection
# (see readme.md) rather than embedding SQL credentials in cribl config.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = ">= 3.2"
    }
  }
}

variable "cribl_host" {
  description = "Cribl leader base URL"
  type        = string
  default     = "http://127.0.0.1:19000"
}
variable "cribl_username" {
  type = string
  validation {
    condition     = length(var.cribl_username) > 0
    error_message = "Cribl username must not be empty."
  }
}
variable "cribl_password" {
  type      = string
  sensitive = true
  validation {
    condition     = length(var.cribl_password) > 0
    error_message = "Cribl password must not be empty."
  }
}
variable "db_connection_id" {
  description = "Existing Cribl database-connection id for the MS-SQL server"
  default     = "mssql_connection"
}
variable "collect_query" {
  description = "SQL collect query; use a checkpoint column for incremental loads"
  default     = "SELECT * FROM dbo.events WHERE modtime > '$${earliest}' ORDER BY modtime"
}
variable "pipeline_id" { default = "my_pipeline" }
variable "pipeline_group" { default = "default" }
variable "source_tag" { default = "mssql_db" }
variable "aggregate_interval" { default = "1m" }
variable "sample_rate" { default = 5 }
variable "limit_max_events" { default = 100000 }
variable "error_output" { default = "error_destination" }
variable "main_output" { default = "default" }
variable "metrics_output" { default = "devnull" }
variable "pipeline_variant" { default = "logs" }

locals {
  pipeline_id_variant = "${var.pipeline_id}_${var.pipeline_variant}"
  config_template     = "${path.module}/../config/pipeline_config.json"
}

resource "null_resource" "create_pipeline" {
  triggers = {
    config_sha  = filesha256(local.config_template)
    pipeline_id = local.pipeline_id_variant
  }
  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    environment = {
      CRIBL_HOST          = var.cribl_host
      CRIBL_USER          = var.cribl_username
      CRIBL_PASS          = var.cribl_password
      GROUP               = var.pipeline_group
      PIPELINE_ID_VARIANT = local.pipeline_id_variant
      SOURCE_TAG          = var.source_tag
      AGG_INTERVAL        = var.aggregate_interval
      SAMPLE_RATE         = var.sample_rate
      LIMIT_EVENTS        = var.limit_max_events
      ERROR_OUTPUT        = var.error_output
      MAIN_OUTPUT         = var.main_output
      METRICS_OUTPUT      = var.metrics_output
      JSON_FILE           = local.config_template
    }
    command = <<-EOT
      set -euo pipefail
      TOKEN=$(curl -s -X POST "$CRIBL_HOST/api/v1/auth/login" -H 'Content-Type: application/json' -d "{\"username\":\"$CRIBL_USER\",\"password\":\"$CRIBL_PASS\"}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
      [ -n "$TOKEN" ] || { echo "Cribl API login failed"; exit 1; }
      AUTH_HEADER="Authorization: Bearer $TOKEN"
      STATUS=$(curl -s -o /dev/null -w "%%{http_code}" -H "$AUTH_HEADER" "$CRIBL_HOST/api/v1/m/$GROUP/pipelines/$PIPELINE_ID_VARIANT")
      if [ "$STATUS" = "200" ]; then
        echo "Pipeline $PIPELINE_ID_VARIANT exists."
        exit 0
      fi
      TMP=$(mktemp)
      sed -e "s/{{pipeline_id}}/$PIPELINE_ID_VARIANT/g" \
          -e "s/{{source_tag}}/$SOURCE_TAG/g" \
          -e "s/{{aggregate_interval}}/$AGG_INTERVAL/g" \
          -e "s/{{sample_rate}}/$SAMPLE_RATE/g" \
          -e "s/{{limit_max_events}}/$LIMIT_EVENTS/g" \
          -e "s/{{error_output}}/$ERROR_OUTPUT/g" \
          -e "s/{{main_output}}/$MAIN_OUTPUT/g" \
          -e "s/{{metrics_destination}}/$METRICS_OUTPUT/g" \
          "$JSON_FILE" > "$TMP"
      curl -sf -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" \
        "$CRIBL_HOST/api/v1/m/$GROUP/pipelines" -d @"$TMP" > /dev/null
      rm -f "$TMP"
      echo "Pipeline $PIPELINE_ID_VARIANT created."
    EOT
  }
}

resource "null_resource" "create_collector" {
  triggers = {
    pipeline_id = local.pipeline_id_variant
    connection  = var.db_connection_id
    query_sha   = sha256(var.collect_query)
  }
  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    environment = {
      CRIBL_HOST          = var.cribl_host
      CRIBL_USER          = var.cribl_username
      CRIBL_PASS          = var.cribl_password
      GROUP               = var.pipeline_group
      PIPELINE_ID_VARIANT = local.pipeline_id_variant
      DB_CONNECTION_ID    = var.db_connection_id
      COLLECT_QUERY       = var.collect_query
    }
    command = <<-EOT
      set -euo pipefail
      TOKEN=$(curl -s -X POST "$CRIBL_HOST/api/v1/auth/login" -H 'Content-Type: application/json' -d "{\"username\":\"$CRIBL_USER\",\"password\":\"$CRIBL_PASS\"}" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
      [ -n "$TOKEN" ] || { echo "Cribl API login failed"; exit 1; }
      AUTH_HEADER="Authorization: Bearer $TOKEN"
      EXISTS=$(curl -s -o /dev/null -w "%%{http_code}" -H "$AUTH_HEADER" "$CRIBL_HOST/api/v1/m/$GROUP/lib/jobs/mssql_collector")
      if [ "$EXISTS" = "200" ]; then
        echo "Collector mssql_collector exists; skipping."
        exit 0
      fi
      PAYLOAD=$(cat <<JSON
      {
        "id": "mssql_collector",
        "type": "collection",
        "ttl": "4h",
        "removeFields": [],
        "resumeOnBoot": false,
        "schedule": {"cronSchedule": "0 2 * * *", "maxConcurrentRuns": 1, "skippable": true, "run": {"rescheduleDroppedTasks": true, "maxTaskReschedule": 1, "logLevel": "info", "jobTimeout": "0", "mode": "run", "timeRangeType": "relative", "timestampTimezone": "UTC", "expression": "true", "minTaskSize": "1MB", "maxTaskSize": "10MB"}},
        "collector": {"type": "database", "conf": {"connectionId": "$DB_CONNECTION_ID", "query": "$COLLECT_QUERY"}},
        "input": {"type": "collection", "staleChannelFlushMs": 10000, "sendToRoutes": false, "preprocess": {"disabled": true}, "throttleRatePerSec": "0", "pipeline": "$PIPELINE_ID_VARIANT", "output": "default"}
      }
      JSON
      )
      STATUS=$(curl -s -o /tmp/cribl_collector_resp.json -w "%%{http_code}" -X POST \
        -H "$AUTH_HEADER" -H "Content-Type: application/json" \
        "$CRIBL_HOST/api/v1/m/$GROUP/lib/jobs" -d "$PAYLOAD")
      case "$STATUS" in
        200|201) echo "Collector created." ;;
        409) echo "Collector exists; skipping." ;;
        *) echo "Collector creation failed ($STATUS): $(cat /tmp/cribl_collector_resp.json)"; exit 1 ;;
      esac
    EOT
  }
  depends_on = [null_resource.create_pipeline]
}

output "pipeline_id" {
  value = local.pipeline_id_variant
}
