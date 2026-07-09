variable "cluster_name" {
  description = "Name of the Nomad cluster"
  type        = string
  validation {
    condition     = length(var.cluster_name) >= 3 && length(var.cluster_name) <= 50 && can(regex("^[a-zA-Z0-9-]+$", var.cluster_name))
    error_message = "Cluster name must be 3-50 characters long and contain only letters, numbers, or hyphens."
  }
}

variable "instance_type" {
  description = "EC2 instance type for Nomad nodes"
  type        = string
  default     = "t3.medium"
  validation {
    condition     = can(regex("^[a-z0-9]+\\.[a-z0-9]+$", var.instance_type))
    error_message = "Instance type must be a valid AWS EC2 instance type (e.g., t3.medium)."
  }
}

variable "ami_id" {
  description = "AMI ID for Nomad nodes"
  type        = string
  validation {
    condition     = can(regex("^ami-[0-9a-f]{17}$", var.ami_id))
    error_message = "AMI ID must be a valid AWS AMI ID (e.g., ami-1234567890abcdef0)."
  }
}

variable "vpc_id" {
  description = "VPC ID for the Nomad cluster"
  type        = string
  validation {
    condition     = can(regex("^vpc-[0-9a-f]{17}$", var.vpc_id))
    error_message = "VPC ID must be a valid AWS VPC ID (e.g., vpc-1234567890abcdef0)."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs for the Nomad ASG"
  type        = list(string)
  validation {
    condition     = length(var.subnet_ids) > 0 && alltrue([for id in var.subnet_ids : can(regex("^subnet-[0-9a-f]{17}$", id))])
    error_message = "Subnet IDs must be a non-empty list of valid AWS subnet IDs (e.g., subnet-1234567890abcdef0)."
  }
}

variable "desired_capacity" {
  description = "Desired number of Nomad instances"
  type        = number
  default     = 3
  validation {
    condition     = var.desired_capacity >= 1 && var.desired_capacity <= 10
    error_message = "Desired capacity must be between 1 and 10."
  }
}

variable "secrets_arn" {
  description = "ARN of the AWS Secrets Manager secret for Nomad tokens"
  type        = string
  validation {
    condition     = can(regex("^arn:aws:secretsmanager:[a-z0-9-]+:[0-9]+:secret:[a-zA-Z0-9-/]+$", var.secrets_arn))
    error_message = "Secrets ARN must be a valid AWS Secrets Manager ARN."
  }
}

variable "nomad_version" {
  description = "Nomad version to install"
  type        = string
  default     = "2.0.3"
  validation {
    condition     = can(regex("^\\d+\\.\\d+\\.\\d+$", var.nomad_version))
    error_message = "Nomad version must be in the format X.Y.Z (e.g., 2.0.3)."
  }
}

variable "aws_region" {
  description = "AWS region of the Secrets Manager secret (always the primary region, even for secondary-region instances)"
  type        = string
}

variable "podman_enabled" {
  description = "Enable Podman driver for Nomad"
  type        = bool
  default     = true
}

variable "client_enabled" {
  description = "Enable Nomad client mode"
  type        = bool
  default     = false
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

variable "workload_ingress_cidr_blocks" {
  description = "CIDRs allowed to reach workloads on 80/443; empty list disables workload ingress"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "vault_address" {
  description = "Vault API address (internal NLB); empty disables the vault stanza"
  type        = string
  default     = ""
}

variable "snapshot_s3_bucket" {
  description = "S3 bucket for daily Raft snapshots (servers only); empty disables snapshot backups"
  type        = string
  default     = ""
}

variable "csi_enabled" {
  description = "Grant EC2 volume permissions for the EBS CSI plugin (clients only)"
  type        = bool
  default     = false
}

variable "autoscaler_enabled" {
  description = "Grant autoscaling permissions for the Nomad Autoscaler (clients only)"
  type        = bool
  default     = false
}
