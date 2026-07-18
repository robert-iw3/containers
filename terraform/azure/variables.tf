variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus"
}

variable "name_prefix" {
  description = "Prefix for all resource names and join tags."
  type        = string
  default     = "hashistack"
}

variable "vnet_cidr" {
  description = "Virtual network CIDR."
  type        = string
  default     = "10.61.0.0/16"
}

variable "allowed_admin_cidrs" {
  description = "CIDRs allowed to reach SSH and the product UIs/APIs. Lock this down."
  type        = list(string)
  default     = []
}

variable "admin_username" {
  description = "VM admin username."
  type        = string
  default     = "hashiadmin"
}

variable "admin_ssh_public_key" {
  description = "SSH public key for the VM admin user."
  type        = string
}

variable "vm_size" {
  description = "VM size for all roles."
  type        = string
  default     = "Standard_B2s"
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

variable "db_sku" {
  description = "PostgreSQL flexible server SKU."
  type        = string
  default     = "B_Standard_B1ms"
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
  type    = map(string)
  default = {}
}
