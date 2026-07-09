variable "ami" {
  description = "AMI ID for the instance"
  type        = string
  validation {
    condition     = length(var.ami) > 4 && substr(var.ami, 0, 4) == "ami-"
    error_message = "The AMI ID must start with 'ami-'."
  }
}

variable "instance_type" {
  description = "Instance type for the instance"
  type        = string
  default     = "t3.micro"
  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium", "t2.micro", "t2.small"], var.instance_type)
    error_message = "Instance type must be one of: t3.micro, t3.small, t3.medium, t2.micro, t2.small."
  }
}

variable "db_details" {
  description = "Details of the database connection"
  type = object({
    name     = string
    username = string
    password = string
    port     = number
    address  = string
  })
  sensitive = true
}

variable "core_url" {
  description = "URL of the Defguard instance"
  type        = string
  validation {
    condition     = can(regex("^https?://", var.core_url))
    error_message = "Core URL must start with http:// or https://."
  }
}

variable "proxy_address" {
  description = "The IP address of the Defguard Proxy instance"
  type        = string
  validation {
    condition     = can(regex("^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$", var.proxy_address))
    error_message = "Proxy address must be a valid IPv4 address."
  }
}

variable "proxy_grpc_port" {
  description = "Port to be used to communicate with Defguard Proxy"
  type        = number
  validation {
    condition     = var.proxy_grpc_port >= 1024 && var.proxy_grpc_port <= 65535
    error_message = "Proxy gRPC port must be between 1024 and 65535."
  }
}

variable "proxy_url" {
  description = "The URL of the Defguard Proxy instance where enrollment is performed"
  type        = string
  validation {
    condition     = can(regex("^https?://", var.proxy_url))
    error_message = "Proxy URL must start with http:// or https://."
  }
}

variable "grpc_port" {
  description = "Port to be used to communicate with Defguard Core"
  type        = number
  validation {
    condition     = var.grpc_port >= 1024 && var.grpc_port <= 65535
    error_message = "gRPC port must be between 1024 and 65535."
  }
}

variable "http_port" {
  description = "Port to be used to access Defguard Core via HTTP"
  type        = number
  default     = 8000
  validation {
    condition     = var.http_port >= 80 && var.http_port <= 65535
    error_message = "HTTP port must be between 80 and 65535."
  }
}

variable "gateway_secret" {
  description = "Secret for the Defguard Gateway"
  type        = string
  sensitive   = true
}

variable "network_interface_id" {
  description = "Network interface ID for the instance"
  type        = string
}

variable "vpn_networks" {
  description = "List of VPN networks"
  type = list(object({
    name     = string
    address  = string
    port     = number
    endpoint = string
    id       = number
  }))
  validation {
    condition     = alltrue([for net in var.vpn_networks : can(regex("^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}/[0-9]{1,2}$", net.address))])
    error_message = "Each VPN network address must be a valid CIDR."
  }
}

variable "package_version" {
  description = "Version of the Defguard Core package to be installed"
  type        = string
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.package_version))
    error_message = "Package version must be in the format X.Y.Z."
  }
}

variable "arch" {
  description = "Architecture of the Defguard Core package to be installed"
  type        = string
  validation {
    condition     = contains(["x86_64", "aarch64"], var.arch)
    error_message = "Architecture must be either 'x86_64' or 'aarch64'."
  }
}

variable "default_admin_password" {
  description = "Default admin password for the Defguard Core"
  type        = string
  sensitive   = true
  default     = "pass123"
}

variable "cookie_insecure" {
  description = "Whether to use insecure cookies for the Defguard Core"
  type        = bool
}

variable "log_level" {
  description = "Log level for Defguard Core. Possible values: trace, debug, info, warn, error"
  type        = string
  default     = "info"
  validation {
    condition     = contains(["trace", "debug", "info", "warn", "error"], var.log_level)
    error_message = "Log level must be one of: trace, debug, info, warn, error."
  }
}