variable "product" {
  description = "HashiCorp product to install (consul, vault, boundary)."
  type        = string
  validation {
    condition     = contains(["consul", "vault", "boundary"], var.product)
    error_message = "product must be one of: consul, vault, boundary."
  }
}

variable "product_version" {
  description = "Product version to install from releases.hashicorp.com."
  type        = string
}

variable "config" {
  description = "Rendered server configuration written to /etc/<product>.d/server.hcl. Occurrences of __PRIVATE_IP__ and __HOSTNAME__ are substituted at boot."
  type        = string
}

variable "exec_start" {
  description = "systemd ExecStart line for the service."
  type        = string
}

variable "extra_files" {
  description = "Additional files to write before the service starts, keyed by absolute path (e.g. TLS material)."
  type        = map(string)
  default     = {}
}

variable "env_content" {
  description = "Optional content for /etc/<product>.d/<product>.env, loaded by the unit as EnvironmentFile (e.g. database URLs)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "extra_setup" {
  description = "Optional shell snippet executed after install but before the service starts (e.g. 'boundary database init')."
  type        = string
  default     = ""
}
