data "aws_secretsmanager_secret_version" "splunk_secrets" {
  secret_id = var.secrets_id
  count     = var.deployment_type == "aws" ? 1 : 0
}

resource "aws_launch_template" "splunk_template" {
  name_prefix   = "splunk-launch-template"
  image_id      = jsondecode(data.aws_secretsmanager_secret_version.splunk_secrets[0].secret_string)["ami_id"]
  instance_type = var.instance_type
  key_name      = jsondecode(data.aws_secretsmanager_secret_version.splunk_secrets[0].secret_string)["key_name"]
  count         = var.deployment_type == "aws" ? 1 : 0

  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size = var.indexing_volume
      encrypted   = true
    }
  }

  user_data = base64encode(<<-EOF
              #!/bin/bash
              echo "ansible_user=admin" >> /etc/ansible/hosts
              EOF
  )

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "splunk_asg" {
  name                = "splunk-asg"
  max_size            = 1
  min_size            = 1
  desired_capacity    = 1
  vpc_zone_identifier = [jsondecode(data.aws_secretsmanager_secret_version.splunk_secrets[0].secret_string)["subnet_id"]]
  count               = var.deployment_type == "aws" ? 1 : 0

  launch_template {
    id      = aws_launch_template.splunk_template[0].id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "splunk-enterprise"
    propagate_at_launch = true
  }
}

resource "aws_security_group" "splunk_sg" {
  name        = "splunk-security-group"
  description = "Security group for Splunk Enterprise"
  vpc_id      = jsondecode(data.aws_secretsmanager_secret_version.splunk_secrets[0].secret_string)["vpc_id"]
  count       = var.deployment_type == "aws" ? 1 : 0

  dynamic "ingress" {
    for_each = [
      { port = 8000, protocol = "tcp" },
      { port = 8089, protocol = "tcp" },
      { port = 8088, protocol = "tcp" },
      { port = 5140, protocol = "tcp" },
      { port = 5141, protocol = "udp" },
      { port = 514, protocol = "tcp" },
      { port = 22, protocol = "tcp" }
    ]
    content {
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = ingress.value.protocol
      cidr_blocks = [var.allowed_cidr]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "splunk_role" {
  name  = "splunk_role"
  count = var.deployment_type == "aws" ? 1 : 0

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "splunk_policy" {
  name  = "splunk_policy"
  role  = aws_iam_role.splunk_role[0].id
  count = var.deployment_type == "aws" ? 1 : 0

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Effect = "Allow"
        Resource = [
          "arn:aws:s3:::splunk-terraform-state/*",
          "arn:aws:s3:::splunk-terraform-state"
        ]
      },
      {
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem"
        ]
        Effect = "Allow"
        Resource = "arn:aws:dynamodb:*:*:table/splunk-terraform-locks"
      },
      {
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Effect = "Allow"
        Resource = "arn:aws:secretsmanager:*:*:secret:splunk-secrets-*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "splunk_profile" {
  name  = "splunk_profile"
  role  = aws_iam_role.splunk_role[0].name
  count = var.deployment_type == "aws" ? 1 : 0
}

output "splunk_server_public_ip" {
  value = var.deployment_type == "aws" ? aws_autoscaling_group.splunk_asg[0].id : "N/A"
}