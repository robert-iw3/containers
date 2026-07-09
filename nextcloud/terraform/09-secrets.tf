# Database Secrets
data "aws_secretsmanager_secret_version" "db_secret_1" {
  secret_id = var.db_secret_1_arn
}

locals {
  rds_db_credentials_1 = jsondecode(data.aws_secretsmanager_secret_version.db_secret_1.secret_string)
}

# Nextcloud Secrets
data "aws_secretsmanager_secret_version" "nextcloud_secret_1" {
  secret_id = var.nextcloud_secret_1_arn
}

locals {
  nextcloud_credentials_1 = jsondecode(data.aws_secretsmanager_secret_version.nextcloud_secret_1.secret_string)
}
