variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix for all resource names and join tags."
  type        = string
  default     = "hashistack"
}

variable "vpc_cidr" {
  description = "VPC CIDR block."
  type        = string
  default     = "10.60.0.0/16"
}

variable "allowed_admin_cidrs" {
  description = "CIDRs allowed to reach SSH and the product UIs/APIs. Lock this down."
  type        = list(string)
  default     = []
}

variable "key_name" {
  description = "Optional EC2 key pair name for SSH."
  type        = string
  default     = null
}

variable "instance_type" {
  description = "Instance type per role."
  type        = map(string)
  default = {
    consul   = "t3.small"
    vault    = "t3.small"
    boundary = "t3.small"
  }
}

variable "consul_servers" {
  description = "Number of Consul servers (odd, 3 or 5)."
  type        = number
  default     = 3
}

variable "vault_servers" {
  description = "Number of Vault servers (odd, 3 or 5)."
  type        = number
  default     = 3
}

variable "boundary_workers" {
  description = "Number of Boundary workers."
  type        = number
  default     = 1
}

variable "db_instance_class" {
  description = "RDS instance class for the Boundary database."
  type        = string
  default     = "db.t4g.micro"
}

variable "datacenter" {
  description = "Consul datacenter name."
  type        = string
  default     = "dc1"
}

variable "consul_version" {
  type    = string
  default = "2.0.2"
}

variable "vault_version" {
  type    = string
  default = "2.0.3"
}

variable "boundary_version" {
  type    = string
  default = "0.21.3"
}

variable "tags" {
  description = "Extra tags for all resources."
  type        = map(string)
  default     = {}
}
