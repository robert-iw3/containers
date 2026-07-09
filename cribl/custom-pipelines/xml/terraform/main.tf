provider "cribl" {
  host     = "https://your-cribl-instance.example.com"
  username = var.cribl_username
  password = var.cribl_password
}

variable "cribl_username" { type = string }
variable "cribl_password" { type = string }
variable "xml_dir" { default = "./xml_files" }
variable "file_filter" { default = "*.xml" }
variable "tracking_field" { default = "modtime" }
variable "pipeline_id" { default = "my_xml_pipeline" }
variable "pipeline_group" { default = "local" }
variable "source_tag" { default = "xml_files" }
variable "aggregate_interval" { default = "1m" }
variable "sample_rate" { default = 0.5 }
variable "limit_max_events" { default = 100000 }
variable "error_output" { default = "error_destination" }
variable "main_output" { default = "main_destination" }
variable "pipeline_variant" { default = "logs" }

# Validations... (same as MS SQL)

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

locals {
  xml_files = fileset(var.xml_dir, var.file_filter)
}

resource "cribl_collector" "xml_collector" {
  for_each    = local.xml_files
  id          = "xml_collector_${replace(each.value, ".xml", "")}"
  type        = "file"
  description = "XML File Collector for ${each.value} with incremental loads"
  config = {
    path               = var.xml_dir
    file_filter        = var.file_filter
    schedule           = "0 2 * * *"
    state_enabled      = true
    tracking_column    = var.tracking_field
    incremental_load   = true
    batch_size         = 5000
    pipeline_id        = "${var.pipeline_id}_${var.pipeline_variant}"
    throttling_rate    = "5 MB"
    max_retries        = 3
    retry_delay        = 10
    connection_timeout = 30000
    request_timeout    = 60000
  }
  depends_on = [null_resource.create_pipeline]
}

output "collector_ids" {
  value = [for c in cribl_collector.xml_collector : c.id]
}

resource "null_resource" "log_creation" {
  provisioner "local-exec" {
    command = "echo '$(date): Created collectors: ${join(", ", values(cribl_collector.xml_collector)[*].id)}' >> terraform_log.txt"
  }
  depends_on = [cribl_collector.xml_collector]
}