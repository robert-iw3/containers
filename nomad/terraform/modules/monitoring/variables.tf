variable "cluster_name" {
  description = "Name of the cluster"
  type        = string
  validation {
    condition     = length(var.cluster_name) >= 3 && length(var.cluster_name) <= 50 && can(regex("^[a-zA-Z0-9-]+$", var.cluster_name))
    error_message = "Cluster name must be 3-50 characters long and contain only letters, numbers, or hyphens."
  }
}

variable "monitoring_ami_id" {
  description = "AMI ID for the monitoring instance"
  type        = string
  validation {
    condition     = can(regex("^ami-[0-9a-f]{17}$", var.monitoring_ami_id))
    error_message = "AMI ID must be a valid AWS AMI ID (e.g., ami-1234567890abcdef0)."
  }
}

variable "instance_type" {
  description = "EC2 instance type for monitoring"
  type        = string
  default     = "t3.medium"
  validation {
    condition     = can(regex("^[a-z0-9]+\\.[a-z0-9]+$", var.instance_type))
    error_message = "Instance type must be a valid AWS EC2 instance type (e.g., t3.medium)."
  }
}

variable "vpc_id" {
  description = "VPC ID for the monitoring instance"
  type        = string
  validation {
    condition     = can(regex("^vpc-[0-9a-f]{17}$", var.vpc_id))
    error_message = "VPC ID must be a valid AWS VPC ID (e.g., vpc-1234567890abcdef0)."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs for the monitoring instance"
  type        = list(string)
  validation {
    condition     = length(var.subnet_ids) > 0 && alltrue([for id in var.subnet_ids : can(regex("^subnet-[0-9a-f]{17}$", id))])
    error_message = "Subnet IDs must be a non-empty list of valid AWS subnet IDs."
  }
}

variable "ssl_certificate_arn" {
  description = "ARN of the SSL certificate for Grafana LB"
  type        = string
  validation {
    condition     = can(regex("^arn:aws:acm:[a-z0-9-]+:[0-9]+:certificate/[0-9a-f-]+$", var.ssl_certificate_arn))
    error_message = "SSL certificate ARN must be a valid AWS ACM ARN."
  }
}

variable "nomad_ips" {
  description = "IP addresses of Nomad instances"
  type        = list(string)
  default     = []
}

variable "aws_region" {
  description = "AWS region of the Secrets Manager secret (always the primary region)"
  type        = string
}

variable "consul_ips" {
  description = "IP addresses of Consul instances"
  type        = list(string)
  default     = []
}

variable "vault_ips" {
  description = "IP addresses of Vault instances"
  type        = list(string)
  default     = []
}

variable "secrets_arn" {
  description = "ARN of the AWS Secrets Manager secret containing the Grafana admin password"
  type        = string
  validation {
    condition     = can(regex("^arn:aws:secretsmanager:[a-z0-9-]+:[0-9]+:secret:[a-zA-Z0-9-/]+$", var.secrets_arn))
    error_message = "Secrets ARN must be a valid AWS Secrets Manager ARN."
  }
}

variable "ssh_key_name" {
  description = "Name of the SSH key pair for EC2 instances"
  type        = string
  default     = ""
  validation {
    condition     = var.ssh_key_name == "" || can(regex("^[a-zA-Z0-9-_]{1,255}$", var.ssh_key_name))
    error_message = "SSH key name must be 1-255 characters long and contain only letters, numbers, hyphens, or underscores."
  }
}
variable "admin_cidr_blocks" {
  description = "CIDRs allowed operator access (SSH, UI/API ports); empty list denies all external admin access"
  type        = list(string)
  default     = []
}
