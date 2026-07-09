variable "cluster_name" {
  description = "Name of the Vault cluster"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for Vault servers"
  type        = string
}

variable "ami_id" {
  description = "AMI ID for Vault nodes"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for the Vault cluster"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the Vault ASG"
  type        = list(string)
}

variable "desired_capacity" {
  description = "Desired number of Vault server instances"
  type        = number
}

variable "vault_enabled" {
  description = "Enable Vault deployment"
  type        = bool
}

variable "ssh_key_name" {
  description = "Name of the SSH key pair for EC2 instances"
  type        = string
  default     = ""
}
variable "admin_cidr_blocks" {
  description = "CIDRs allowed operator access (SSH, UI/API ports); empty list denies all external admin access"
  type        = list(string)
  default     = []
}

variable "cluster_cidr_blocks" {
  description = "VPC/cluster CIDRs allowed to reach the service API (Nomad agents live in these ranges)"
  type        = list(string)
  default     = []
}
