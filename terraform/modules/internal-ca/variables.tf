variable "common_name" {
  description = "Common name for the leaf certificate (e.g. server.dc1.consul)."
  type        = string
}

variable "organization" {
  description = "Certificate organization."
  type        = string
  default     = "HashiCorp Stack"
}

variable "dns_sans" {
  description = "DNS SANs for the leaf certificate."
  type        = list(string)
  default     = []
}

variable "ip_sans" {
  description = "IP SANs for the leaf certificate."
  type        = list(string)
  default     = ["127.0.0.1"]
}

variable "ca_validity_hours" {
  type    = number
  default = 43800 # 5 years
}

variable "leaf_validity_hours" {
  type    = number
  default = 8760 # 1 year
}
