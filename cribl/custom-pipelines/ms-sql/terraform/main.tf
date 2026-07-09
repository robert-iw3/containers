provider "cribl" {
  host     = "https://your-cribl-instance.example.com"
  username = var.cribl_username
  password = var.cribl_password
}

variable "cribl_username" { type = string }
variable "cribl_password" { type = string }
variable "sql_host" { default = "sql.example.com" }
variable "sql_port" { default = 1433 }
variable "sql_db" { default = "mydb" }
variable "sql_user" { type = string }
variable "sql_pass" { type = string }
variable "queries_dir" { default = "./queries" }
variable "pipeline_id" { default = "my_pipeline" }
variable "pipeline_group" { default = "local" }
variable "source_tag" { default = "mssql_db" }
variable "aggregate_interval" { default = "1m" }
variable "sample_rate" { default = 0.5 }
variable "limit_max_events" { default = 100000 }
variable "error_output" { default = "error_destination" }
variable "main_output" { default = "main_destination" }
variable "pipeline_variant" { default = "logs" }

variable "cribl_username" {
  validation {
    condition     = length(var.cribl_username) > 0
    error_message = "Cribl username must not be empty."
  }
}
variable "cribl_password" {
  validation {
    condition     = length(var.cribl_password) > 0
    error_message = "Cribl password must not be empty."
  }
}
variable "queries_dir" {
  validation {
    condition     = length(var.queries_dir) > 0
    error_message = "Queries directory must not be empty."
  }
}

resource "null_resource" "create_pipeline" {
  provisioner "local-exec" {
    command = <<EOT
      AUTH_HEADER="Authorization: Basic $(echo -n ${var.cribl_username}:${var.cribl_password} | base64)"
      PIPELINE_ID="${var.pipeline_id}"
      GROUP="${var.pipeline_group}"
      CRIBL_HOST="https://your-cribl-instance.example.com"
      JSON_FILE="../config/pipeline_config.json"
      VARIANT="${var.pipeline_variant}"
      PIPELINE_ID_VARIANT="$PIPELINE_ID_$VARIANT"

      cp "$JSON_FILE" temp.json
      sed -i "s/{{pipeline_id}}/$PIPELINE_ID_VARIANT/g" temp.json
      sed -i "s/{{source_tag}}/${var.source_tag}/g" temp.json
      sed -i "s/{{aggregate_interval}}/${var.aggregate_interval}/g" temp.json
      sed -i "s/{{sample_rate}}/${var.sample_rate}/g" temp.json
      sed -i "s/{{limit_max_events}}/${var.limit_max_events}/g" temp.json
      sed -i "s/{{error_output}}/${var.error_output}/g" temp.json
      sed -i "s/{{main_output}}/${var.main_output}/g" temp.json

      PAYLOAD=$(cat temp.json)

      STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$CRIBL_HOST/api/v1/m/$GROUP/pipelines/$PIPELINE_ID_VARIANT")
      if [ "$STATUS" -eq 200 ]; then
        echo "Pipeline $PIPELINE_ID_VARIANT exists."
        rm temp.json
        exit 0
      fi

      curl -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" \
        "$CRIBL_HOST/api/v1/m/$GROUP/pipelines" -d "$PAYLOAD"
      rm temp.json
    EOT
  }
}

resource "cribl_connection" "mssql_connection" {
  id          = "mssql_conn"
  type        = "mssql"
  description = "Connection to MS SQL Server"
  config = {
    host     = var.sql_host
    port     = var.sql_port
    database = var.sql_db
    username = var.sql_user
    password = var.sql_pass
  }
  depends_on = [null_resource.create_pipeline]
}

locals {
  query_files = fileset(var.queries_dir, "*.sql")
}

resource "cribl_collector" "db_collector" {
  for_each    = local.query_files
  id          = "mssql_collector_${replace(each.value, ".sql", "")}"
  type        = "database"
  description = "MS SQL Database Collector for ${each.value} with incremental loads"
  config = {
    connection_id      = cribl_connection.mssql_connection.id
    sql_query          = "`${file("${var.queries_dir}/${each.value}")} ${state && state.tracking_ts ? `AND tracking_ts > $${state.tracking_ts.value}` : ''}`"
    schedule           = "0 2 * * *"
    state_enabled      = true
    tracking_column    = "tracking_ts"
    incremental_load   = true
    batch_size         = 5000
    pipeline_id        = "${var.pipeline_id}_${var.pipeline_variant}"
    throttling_rate    = "5 MB"
    max_retries        = 3
    retry_delay        = 10
    connection_timeout = 30000
    request_timeout    = 60000
  }
  depends_on = [cribl_connection.mssql_connection]
}

output "collector_ids" {
  value = [for c in cribl_collector.db_collector : c.id]
}

resource "null_resource" "log_creation" {
  provisioner "local-exec" {
    command = "echo '$(date): Created collectors: ${join(", ", values(cribl_collector.db_collector)[*].id)}' >> terraform_log.txt"
  }
  depends_on = [cribl_collector.db_collector]
}