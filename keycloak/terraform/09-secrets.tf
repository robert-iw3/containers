# Database Secrets
data "aws_secretsmanager_secret_version" "db_secret_1" {
  secret_id = var.db_secret_1_arn
}

locals {
  rds_db_credentials_1 = jsondecode(data.aws_secretsmanager_secret_version.db_secret_1.secret_string)
}

# Keycloak Secrets
data "aws_secretsmanager_secret_version" "keycloak_secret_1" {
  secret_id = var.keycloak_secret_1_arn
}

locals {
  keycloak_credentials_1 = jsondecode(data.aws_secretsmanager_secret_version.keycloak_secret_1.secret_string)
}
