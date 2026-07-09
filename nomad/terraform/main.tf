provider "aws" {
  region = var.aws_region
  alias  = "primary"
}

provider "aws" {
  region = var.secondary_region
  alias  = "secondary"
}

resource "random_uuid" "nomad_acl_token" {
}

resource "random_uuid" "nomad_gossip_key" {
}

resource "random_uuid" "vault_token" {
}

resource "aws_kms_key" "nomad_secrets_key" {
  provider                = aws.primary
  description             = "${var.cluster_name}-nomad-secrets-key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags = {
    Name = "${var.cluster_name}-nomad-secrets-key"
  }
}

resource "aws_secretsmanager_secret" "nomad_secrets" {
  provider   = aws.primary
  name       = "${var.cluster_name}-nomad-secrets"
  kms_key_id = aws_kms_key.nomad_secrets_key.arn

  replica {
    region = var.secondary_region
  }
}

locals {
  secret_arn_parts = split(":", aws_secretsmanager_secret.nomad_secrets.arn)
  secondary_secrets_arn = join(":", concat(
    slice(local.secret_arn_parts, 0, 3),
    [var.secondary_region],
    slice(local.secret_arn_parts, 4, length(local.secret_arn_parts))
  ))
}

resource "aws_secretsmanager_secret_version" "nomad_secrets_version" {
  provider  = aws.primary
  secret_id = aws_secretsmanager_secret.nomad_secrets.id
  secret_string = jsonencode({
    nomad_acl_token        = random_uuid.nomad_acl_token.result
    nomad_gossip_key       = random_uuid.nomad_gossip_key.result
    vault_token            = random_uuid.vault_token.result
    grafana_admin_password = var.grafana_admin_password
  })
}

resource "aws_iam_role" "grafana_password_rotation" {
  provider = aws.primary
  name     = "${var.cluster_name}-grafana-password-rotation"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "grafana_password_rotation_policy" {
  provider = aws.primary
  name     = "${var.cluster_name}-grafana-password-rotation-policy"
  role     = aws_iam_role.grafana_password_rotation.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:PutSecretValue",
          "secretsmanager:GetSecretValue",
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [
          aws_secretsmanager_secret.nomad_secrets.arn,
          aws_kms_key.nomad_secrets_key.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

data "archive_file" "grafana_password_rotation" {
  type        = "zip"
  source_file = "${path.module}/lambda/grafana_password_rotation.py"
  output_path = "${path.module}/lambda/grafana_password_rotation.zip"
}

resource "aws_lambda_function" "grafana_password_rotation" {
  provider         = aws.primary
  filename         = data.archive_file.grafana_password_rotation.output_path
  function_name    = "${var.cluster_name}-grafana-password-rotation"
  role             = aws_iam_role.grafana_password_rotation.arn
  handler          = "grafana_password_rotation.lambda_handler"
  runtime          = "python3.13"
  timeout          = 30
  source_code_hash = data.archive_file.grafana_password_rotation.output_base64sha256
}

resource "aws_cloudwatch_event_rule" "grafana_password_rotation_schedule" {
  provider            = aws.primary
  name                = "${var.cluster_name}-grafana-password-rotation-schedule"
  schedule_expression = "rate(1 day)"
}

resource "aws_cloudwatch_event_target" "grafana_password_rotation_target" {
  provider  = aws.primary
  rule      = aws_cloudwatch_event_rule.grafana_password_rotation_schedule.name
  target_id = "GrafanaPasswordRotation"
  arn       = aws_lambda_function.grafana_password_rotation.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  provider      = aws.primary
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.grafana_password_rotation.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.grafana_password_rotation_schedule.arn
}

resource "aws_sns_topic" "budget_notifications" {
  provider = aws.primary
  name     = "${var.cluster_name}-budget-notifications"
}

resource "aws_budgets_budget" "nomad_budget" {
  provider          = aws.primary
  name              = "${var.cluster_name}-budget"
  budget_type       = "COST"
  limit_amount      = "1000"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2025-01-01_00:00"
  time_period_end   = "2030-01-01_00:00"

  notification {
    notification_type         = "ACTUAL"
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_notifications.arn]
  }
}

module "vpc_primary" {
  source       = "./modules/vpc"
  aws_region   = var.aws_region
  cluster_name = "${var.cluster_name}-primary"
  providers = {
    aws = aws.primary
  }
}

module "vpc_secondary" {
  source       = "./modules/vpc"
  aws_region   = var.secondary_region
  cluster_name = "${var.cluster_name}-secondary"
  providers = {
    aws = aws.secondary
  }
}

module "nomad_servers_primary" {
  source                       = "./modules/nomad-cluster"
  cluster_name                 = "${var.cluster_name}-primary"
  instance_type                = var.server_instance_type
  ami_id                       = var.nomad_ami_id
  vpc_id                       = module.vpc_primary.vpc_id
  subnet_ids                   = module.vpc_primary.subnet_ids
  desired_capacity             = var.num_nomad_servers
  secrets_arn                  = aws_secretsmanager_secret.nomad_secrets.arn
  aws_region                   = var.aws_region
  nomad_version                = var.nomad_version
  podman_enabled               = true
  client_enabled               = false
  ssh_key_name                 = var.ssh_key_name
  snapshot_s3_bucket           = aws_s3_bucket.nomad_snapshots.bucket
  vault_address                = module.vault_cluster_primary.vault_address
  admin_cidr_blocks            = var.admin_cidr_blocks
  workload_ingress_cidr_blocks = var.workload_ingress_cidr_blocks
  providers = {
    aws = aws.primary
  }
}

module "nomad_servers_secondary" {
  source                       = "./modules/nomad-cluster"
  cluster_name                 = "${var.cluster_name}-secondary"
  instance_type                = var.server_instance_type
  ami_id                       = var.nomad_ami_id
  vpc_id                       = module.vpc_secondary.vpc_id
  subnet_ids                   = module.vpc_secondary.subnet_ids
  desired_capacity             = var.num_nomad_servers
  secrets_arn                  = local.secondary_secrets_arn
  aws_region                   = var.secondary_region
  nomad_version                = var.nomad_version
  podman_enabled               = true
  client_enabled               = false
  ssh_key_name                 = var.ssh_key_name
  snapshot_s3_bucket           = aws_s3_bucket.nomad_snapshots.bucket
  vault_address                = module.vault_cluster_secondary.vault_address
  admin_cidr_blocks            = var.admin_cidr_blocks
  workload_ingress_cidr_blocks = var.workload_ingress_cidr_blocks
  providers = {
    aws = aws.secondary
  }
}

module "nomad_clients_primary" {
  source                       = "./modules/nomad-cluster"
  cluster_name                 = "${var.cluster_name}-client-primary"
  instance_type                = var.client_instance_type
  ami_id                       = var.nomad_ami_id
  vpc_id                       = module.vpc_primary.vpc_id
  subnet_ids                   = module.vpc_primary.subnet_ids
  desired_capacity             = var.num_nomad_clients
  secrets_arn                  = aws_secretsmanager_secret.nomad_secrets.arn
  aws_region                   = var.aws_region
  nomad_version                = var.nomad_version
  podman_enabled               = true
  client_enabled               = true
  ssh_key_name                 = var.ssh_key_name
  csi_enabled                  = var.csi_enabled
  autoscaler_enabled           = var.autoscaler_enabled
  vault_address                = module.vault_cluster_primary.vault_address
  admin_cidr_blocks            = var.admin_cidr_blocks
  workload_ingress_cidr_blocks = var.workload_ingress_cidr_blocks
  providers = {
    aws = aws.primary
  }
}

module "nomad_clients_secondary" {
  source                       = "./modules/nomad-cluster"
  cluster_name                 = "${var.cluster_name}-client-secondary"
  instance_type                = var.client_instance_type
  ami_id                       = var.nomad_ami_id
  vpc_id                       = module.vpc_secondary.vpc_id
  subnet_ids                   = module.vpc_secondary.subnet_ids
  desired_capacity             = var.num_nomad_clients
  secrets_arn                  = local.secondary_secrets_arn
  aws_region                   = var.secondary_region
  nomad_version                = var.nomad_version
  podman_enabled               = true
  client_enabled               = true
  ssh_key_name                 = var.ssh_key_name
  csi_enabled                  = var.csi_enabled
  autoscaler_enabled           = var.autoscaler_enabled
  vault_address                = module.vault_cluster_secondary.vault_address
  admin_cidr_blocks            = var.admin_cidr_blocks
  workload_ingress_cidr_blocks = var.workload_ingress_cidr_blocks
  providers = {
    aws = aws.secondary
  }
}

resource "aws_autoscaling_policy" "nomad_clients_scale_up_cpu_primary" {
  provider               = aws.primary
  name                   = "${var.cluster_name}-clients-scale-up-cpu-primary"
  autoscaling_group_name = module.nomad_clients_primary.asg_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = 1
  cooldown               = 300
}

resource "aws_autoscaling_policy" "nomad_clients_scale_down_cpu_primary" {
  provider               = aws.primary
  name                   = "${var.cluster_name}-clients-scale-down-cpu-primary"
  autoscaling_group_name = module.nomad_clients_primary.asg_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = -1
  cooldown               = 300
}

resource "aws_autoscaling_policy" "nomad_clients_scale_up_memory_primary" {
  provider               = aws.primary
  name                   = "${var.cluster_name}-clients-scale-up-memory-primary"
  autoscaling_group_name = module.nomad_clients_primary.asg_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = 1
  cooldown               = 300
}

resource "aws_autoscaling_policy" "nomad_clients_scale_down_memory_primary" {
  provider               = aws.primary
  name                   = "${var.cluster_name}-clients-scale-down-memory-primary"
  autoscaling_group_name = module.nomad_clients_primary.asg_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = -1
  cooldown               = 300
}

resource "aws_cloudwatch_metric_alarm" "nomad_clients_cpu_high_primary" {
  provider            = aws.primary
  alarm_name          = "${var.cluster_name}-clients-cpu-high-primary"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 70
  alarm_description   = "Scale up Nomad clients when CPU exceeds 70% in primary region"
  dimensions = {
    AutoScalingGroupName = module.nomad_clients_primary.asg_name
  }
  alarm_actions = [aws_autoscaling_policy.nomad_clients_scale_up_cpu_primary.arn]
}

resource "aws_cloudwatch_metric_alarm" "nomad_clients_cpu_low_primary" {
  provider            = aws.primary
  alarm_name          = "${var.cluster_name}-clients-cpu-low-primary"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 20
  alarm_description   = "Scale down Nomad clients when CPU is below 20% in primary region"
  dimensions = {
    AutoScalingGroupName = module.nomad_clients_primary.asg_name
  }
  alarm_actions = [aws_autoscaling_policy.nomad_clients_scale_down_cpu_primary.arn]
}

resource "aws_cloudwatch_metric_alarm" "nomad_clients_memory_high_primary" {
  provider            = aws.primary
  alarm_name          = "${var.cluster_name}-clients-memory-high-primary"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 70
  alarm_description   = "Scale up Nomad clients when memory exceeds 70% in primary region"
  dimensions = {
    AutoScalingGroupName = module.nomad_clients_primary.asg_name
  }
  alarm_actions = [aws_autoscaling_policy.nomad_clients_scale_up_memory_primary.arn]
}

resource "aws_cloudwatch_metric_alarm" "nomad_clients_memory_low_primary" {
  provider            = aws.primary
  alarm_name          = "${var.cluster_name}-clients-memory-low-primary"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 20
  alarm_description   = "Scale down Nomad clients when memory is below 20% in primary region"
  dimensions = {
    AutoScalingGroupName = module.nomad_clients_primary.asg_name
  }
  alarm_actions = [aws_autoscaling_policy.nomad_clients_scale_down_memory_primary.arn]
}

resource "aws_autoscaling_policy" "nomad_clients_scale_up_cpu_secondary" {
  provider               = aws.secondary
  name                   = "${var.cluster_name}-clients-scale-up-cpu-secondary"
  autoscaling_group_name = module.nomad_clients_secondary.asg_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = 1
  cooldown               = 300
}

resource "aws_autoscaling_policy" "nomad_clients_scale_down_cpu_secondary" {
  provider               = aws.secondary
  name                   = "${var.cluster_name}-clients-scale-down-cpu-secondary"
  autoscaling_group_name = module.nomad_clients_secondary.asg_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = -1
  cooldown               = 300
}

resource "aws_autoscaling_policy" "nomad_clients_scale_up_memory_secondary" {
  provider               = aws.secondary
  name                   = "${var.cluster_name}-clients-scale-up-memory-secondary"
  autoscaling_group_name = module.nomad_clients_secondary.asg_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = 1
  cooldown               = 300
}

resource "aws_autoscaling_policy" "nomad_clients_scale_down_memory_secondary" {
  provider               = aws.secondary
  name                   = "${var.cluster_name}-clients-scale-down-memory-secondary"
  autoscaling_group_name = module.nomad_clients_secondary.asg_name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = -1
  cooldown               = 300
}

resource "aws_cloudwatch_metric_alarm" "nomad_clients_cpu_high_secondary" {
  provider            = aws.secondary
  alarm_name          = "${var.cluster_name}-clients-cpu-high-secondary"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 70
  alarm_description   = "Scale up Nomad clients when CPU exceeds 70% in secondary region"
  dimensions = {
    AutoScalingGroupName = module.nomad_clients_secondary.asg_name
  }
  alarm_actions = [aws_autoscaling_policy.nomad_clients_scale_up_cpu_secondary.arn]
}

resource "aws_cloudwatch_metric_alarm" "nomad_clients_cpu_low_secondary" {
  provider            = aws.secondary
  alarm_name          = "${var.cluster_name}-clients-cpu-low-secondary"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 20
  alarm_description   = "Scale down Nomad clients when CPU is below 20% in secondary region"
  dimensions = {
    AutoScalingGroupName = module.nomad_clients_secondary.asg_name
  }
  alarm_actions = [aws_autoscaling_policy.nomad_clients_scale_down_cpu_secondary.arn]
}

resource "aws_cloudwatch_metric_alarm" "nomad_clients_memory_high_secondary" {
  provider            = aws.secondary
  alarm_name          = "${var.cluster_name}-clients-memory-high-secondary"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 70
  alarm_description   = "Scale up Nomad clients when memory exceeds 70% in secondary region"
  dimensions = {
    AutoScalingGroupName = module.nomad_clients_secondary.asg_name
  }
  alarm_actions = [aws_autoscaling_policy.nomad_clients_scale_up_memory_secondary.arn]
}

resource "aws_cloudwatch_metric_alarm" "nomad_clients_memory_low_secondary" {
  provider            = aws.secondary
  alarm_name          = "${var.cluster_name}-clients-memory-low-secondary"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 20
  alarm_description   = "Scale down Nomad clients when memory is below 20% in secondary region"
  dimensions = {
    AutoScalingGroupName = module.nomad_clients_secondary.asg_name
  }
  alarm_actions = [aws_autoscaling_policy.nomad_clients_scale_down_memory_secondary.arn]
}

module "consul_cluster_primary" {
  source              = "./modules/consul-cluster"
  cluster_name        = "${var.cluster_name}-primary"
  instance_type       = var.server_instance_type
  ami_id              = var.consul_ami_id
  vpc_id              = module.vpc_primary.vpc_id
  subnet_ids          = module.vpc_primary.subnet_ids
  desired_capacity    = var.num_consul_servers
  consul_enabled      = var.consul_enabled
  ssh_key_name        = var.ssh_key_name
  admin_cidr_blocks   = var.admin_cidr_blocks
  cluster_cidr_blocks = [module.vpc_primary.vpc_cidr]
  providers = {
    aws = aws.primary
  }
}

module "consul_cluster_secondary" {
  source              = "./modules/consul-cluster"
  cluster_name        = "${var.cluster_name}-secondary"
  instance_type       = var.server_instance_type
  ami_id              = var.consul_ami_id
  vpc_id              = module.vpc_secondary.vpc_id
  subnet_ids          = module.vpc_secondary.subnet_ids
  desired_capacity    = var.num_consul_servers
  consul_enabled      = var.consul_enabled
  ssh_key_name        = var.ssh_key_name
  admin_cidr_blocks   = var.admin_cidr_blocks
  cluster_cidr_blocks = [module.vpc_secondary.vpc_cidr]
  providers = {
    aws = aws.secondary
  }
}

module "vault_cluster_primary" {
  source              = "./modules/vault-cluster"
  cluster_name        = "${var.cluster_name}-primary"
  instance_type       = var.server_instance_type
  ami_id              = var.vault_ami_id
  vpc_id              = module.vpc_primary.vpc_id
  subnet_ids          = module.vpc_primary.subnet_ids
  desired_capacity    = var.num_vault_servers
  vault_enabled       = var.vault_enabled
  ssh_key_name        = var.ssh_key_name
  admin_cidr_blocks   = var.admin_cidr_blocks
  cluster_cidr_blocks = [module.vpc_primary.vpc_cidr]
  providers = {
    aws = aws.primary
  }
}

module "vault_cluster_secondary" {
  source              = "./modules/vault-cluster"
  cluster_name        = "${var.cluster_name}-secondary"
  instance_type       = var.server_instance_type
  ami_id              = var.vault_ami_id
  vpc_id              = module.vpc_secondary.vpc_id
  subnet_ids          = module.vpc_secondary.subnet_ids
  desired_capacity    = var.num_vault_servers
  vault_enabled       = var.vault_enabled
  ssh_key_name        = var.ssh_key_name
  admin_cidr_blocks   = var.admin_cidr_blocks
  cluster_cidr_blocks = [module.vpc_secondary.vpc_cidr]
  providers = {
    aws = aws.secondary
  }
}

module "monitoring_primary" {
  source              = "./modules/monitoring"
  cluster_name        = "${var.cluster_name}-primary"
  monitoring_ami_id   = var.nomad_ami_id
  instance_type       = var.server_instance_type
  vpc_id              = module.vpc_primary.vpc_id
  subnet_ids          = module.vpc_primary.subnet_ids
  ssl_certificate_arn = var.ssl_certificate_arn
  nomad_ips           = module.nomad_servers_primary.instance_ips
  consul_ips          = module.consul_cluster_primary.instance_ips
  vault_ips           = module.vault_cluster_primary.instance_ips
  secrets_arn         = aws_secretsmanager_secret.nomad_secrets.arn
  aws_region          = var.aws_region
  ssh_key_name        = var.ssh_key_name
  admin_cidr_blocks   = var.admin_cidr_blocks
  providers = {
    aws = aws.primary
  }
}

module "monitoring_secondary" {
  source              = "./modules/monitoring"
  cluster_name        = "${var.cluster_name}-secondary"
  monitoring_ami_id   = var.nomad_ami_id
  instance_type       = var.server_instance_type
  vpc_id              = module.vpc_secondary.vpc_id
  subnet_ids          = module.vpc_secondary.subnet_ids
  ssl_certificate_arn = var.ssl_certificate_arn
  nomad_ips           = module.nomad_servers_secondary.instance_ips
  consul_ips          = module.consul_cluster_secondary.instance_ips
  vault_ips           = module.vault_cluster_secondary.instance_ips
  secrets_arn         = local.secondary_secrets_arn
  aws_region          = var.secondary_region
  ssh_key_name        = var.ssh_key_name
  admin_cidr_blocks   = var.admin_cidr_blocks
  providers = {
    aws = aws.secondary
  }
}

output "secrets_arn" {
  description = "ARN of the AWS Secrets Manager secret"
  value       = aws_secretsmanager_secret.nomad_secrets.arn
}

output "nomad_server_ips_primary" {
  description = "Private IPs of Nomad server instances in primary region"
  value       = module.nomad_servers_primary.instance_ips
}

output "nomad_server_ips_secondary" {
  description = "Private IPs of Nomad server instances in secondary region"
  value       = module.nomad_servers_secondary.instance_ips
}

output "nomad_client_ips_primary" {
  description = "Private IPs of Nomad client instances in primary region"
  value       = module.nomad_clients_primary.instance_ips
}

output "nomad_client_ips_secondary" {
  description = "Private IPs of Nomad client instances in secondary region"
  value       = module.nomad_clients_secondary.instance_ips
}

output "consul_instance_ips_primary" {
  description = "Private IPs of Consul instances in primary region"
  value       = module.consul_cluster_primary.instance_ips
}

output "consul_instance_ips_secondary" {
  description = "Private IPs of Consul instances in secondary region"
  value       = module.consul_cluster_secondary.instance_ips
}

output "vault_instance_ips_primary" {
  description = "Private IPs of Vault instances in primary region"
  value       = module.vault_cluster_primary.instance_ips
}

output "vault_instance_ips_secondary" {
  description = "Private IPs of Vault instances in secondary region"
  value       = module.vault_cluster_secondary.instance_ips
}

output "grafana_lb_address_primary" {
  description = "DNS name of the Grafana load balancer in primary region"
  value       = module.monitoring_primary.grafana_lb_address
}

output "grafana_lb_address_secondary" {
  description = "DNS name of the Grafana load balancer in secondary region"
  value       = module.monitoring_secondary.grafana_lb_address
}

output "budget_notifications_topic_arn" {
  description = "ARN of the SNS topic for budget notifications"
  value       = aws_sns_topic.budget_notifications.arn
}
resource "aws_s3_bucket" "nomad_snapshots" {
  provider      = aws.primary
  bucket_prefix = "${var.cluster_name}-nomad-snapshots-"
}

resource "aws_s3_bucket_public_access_block" "nomad_snapshots" {
  provider                = aws.primary
  bucket                  = aws_s3_bucket.nomad_snapshots.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "nomad_snapshots" {
  provider = aws.primary
  bucket   = aws_s3_bucket.nomad_snapshots.id

  rule {
    id     = "expire-old-snapshots"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "nomad_snapshots" {
  provider = aws.primary
  bucket   = aws_s3_bucket.nomad_snapshots.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_sns_topic" "cluster_alerts_primary" {
  provider = aws.primary
  name     = "${var.cluster_name}-cluster-alerts"
}

resource "aws_sns_topic" "cluster_alerts_secondary" {
  provider = aws.secondary
  name     = "${var.cluster_name}-cluster-alerts"
}

resource "aws_sns_topic_subscription" "cluster_alerts_email_primary" {
  provider  = aws.primary
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.cluster_alerts_primary.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_sns_topic_subscription" "cluster_alerts_email_secondary" {
  provider  = aws.secondary
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.cluster_alerts_secondary.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "nomad_servers_unhealthy_primary" {
  provider            = aws.primary
  alarm_name          = "${var.cluster_name}-nomad-servers-unhealthy-primary"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "GroupInServiceInstances"
  namespace           = "AWS/AutoScaling"
  period              = 60
  statistic           = "Minimum"
  threshold           = var.num_nomad_servers
  alarm_description   = "Fewer Nomad servers in service than required for quorum in the primary region"
  alarm_actions       = [aws_sns_topic.cluster_alerts_primary.arn]
  ok_actions          = [aws_sns_topic.cluster_alerts_primary.arn]
  dimensions = {
    AutoScalingGroupName = module.nomad_servers_primary.asg_name
  }
}

resource "aws_cloudwatch_metric_alarm" "nomad_servers_unhealthy_secondary" {
  provider            = aws.secondary
  alarm_name          = "${var.cluster_name}-nomad-servers-unhealthy-secondary"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "GroupInServiceInstances"
  namespace           = "AWS/AutoScaling"
  period              = 60
  statistic           = "Minimum"
  threshold           = var.num_nomad_servers
  alarm_description   = "Fewer Nomad servers in service than required for quorum in the secondary region"
  alarm_actions       = [aws_sns_topic.cluster_alerts_secondary.arn]
  ok_actions          = [aws_sns_topic.cluster_alerts_secondary.arn]
  dimensions = {
    AutoScalingGroupName = module.nomad_servers_secondary.asg_name
  }
}
