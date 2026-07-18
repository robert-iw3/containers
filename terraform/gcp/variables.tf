variable "project_id" {
  description = "GCP project id."
  type        = string
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone."
  type        = string
  default     = "us-central1-a"
}

variable "name_prefix" {
  description = "Prefix for all resource names and join tags."
  type        = string
  default     = "hashistack"
}

variable "subnet_cidr" {
  description = "Subnetwork CIDR."
  type        = string
  default     = "10.62.0.0/16"
}

variable "allowed_admin_cidrs" {
  description = "CIDRs allowed to reach SSH and the product UIs/APIs. Lock this down."
  type        = list(string)
  default     = []
}

variable "machine_type" {
  description = "Machine type for all roles."
  type        = string
  default     = "e2-small"
}

variable "consul_servers" {
  type    = number
  default = 3
}

variable "vault_servers" {
  type    = number
  default = 3
}

variable "boundary_workers" {
  type    = number
  default = 1
}

variable "datacenter" {
  description = "Consul datacenter name."
  type        = string
  default     = "dc1"
}

variable "db_tier" {
  description = "Cloud SQL tier for the Boundary database."
  type        = string
  default     = "db-f1-micro"
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

variable "labels" {
  type    = map(string)
  default = {}
}
