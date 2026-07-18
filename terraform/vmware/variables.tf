variable "vsphere_server" {
  description = "vCenter server address (or set TF_VAR_vsphere_server)."
  type        = string
  default     = ""
}

variable "vsphere_user" {
  description = "vCenter username (or set TF_VAR_vsphere_user)."
  type        = string
  default     = ""
}

variable "vsphere_password" {
  description = "vCenter password (set via TF_VAR_vsphere_password)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "allow_unverified_ssl" {
  description = "Skip vCenter TLS verification (lab environments only)."
  type        = bool
  default     = false
}

variable "name_prefix" {
  description = "Prefix for all VM names."
  type        = string
  default     = "hashistack"
}

variable "datacenter" {
  description = "vSphere datacenter name."
  type        = string
}

variable "cluster" {
  description = "vSphere compute cluster name."
  type        = string
}

variable "datastore" {
  description = "vSphere datastore name."
  type        = string
}

variable "network" {
  description = "vSphere port group / network name."
  type        = string
}

variable "template" {
  description = "Ubuntu cloud image template with cloud-init + VMware guestinfo datasource (e.g. imported from the official Ubuntu 24.04 OVA)."
  type        = string
}

variable "folder" {
  description = "Optional VM folder."
  type        = string
  default     = null
}

variable "num_cpus" {
  type    = number
  default = 2
}

variable "memory_mb" {
  type    = number
  default = 4096
}

variable "disk_gb" {
  type    = number
  default = 40
}

# --- static addressing ------------------------------------------------------

variable "network_prefix_length" {
  description = "Prefix length of the VM network, e.g. 24."
  type        = number
  default     = 24
}

variable "gateway" {
  description = "Default gateway for the VM network."
  type        = string
}

variable "dns_servers" {
  description = "DNS servers."
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]
}

variable "consul_ips" {
  description = "Static IPs for the Consul servers (3 or 5)."
  type        = list(string)
}

variable "vault_ips" {
  description = "Static IPs for the Vault servers (3 or 5)."
  type        = list(string)
}

variable "boundary_controller_ip" {
  description = "Static IP for the Boundary controller."
  type        = string
}

variable "boundary_worker_ips" {
  description = "Static IPs for the Boundary workers."
  type        = list(string)
}

variable "postgres_ip" {
  description = "Static IP for the PostgreSQL VM backing Boundary."
  type        = string
}

variable "consul_datacenter" {
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
