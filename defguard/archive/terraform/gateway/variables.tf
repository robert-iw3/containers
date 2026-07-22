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

variable "gateway_port" {
  description = "Port to be used by the VPN"
  type        = number
  default     = 50051
  validation {
    condition     = var.gateway_port >= 1024 && var.gateway_port <= 65535
    error_message = "Gateway port must be between 1024 and 65535."
  }
}

variable "gateway_secret" {
  description = "Secret key for the Defguard Gateway"
  type        = string
  sensitive   = true
}

variable "network_id" {
  description = "ID of the VPN network"
  type        = number
  validation {
    condition     = var.network_id >= 1
    error_message = "Network ID must be a positive integer."
  }
}

variable "core_address" {
  description = "Internal address of the Defguard instance"
  type        = string
  validation {
    condition     = can(regex("^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$", var.core_address))
    error_message = "Core address must be a valid IPv4 address."
  }
}

variable "core_grpc_port" {
  description = "Port to be used to communicate with Defguard Core"
  type        = number
  validation {
    condition     = var.core_grpc_port >= 1024 && var.core_grpc_port <= 65535
    error_message = "Core gRPC port must be between 1024 and 65535."
  }
}

variable "network_interface_id" {
  description = "Network interface ID for the instance"
  type        = string
}

variable "package_version" {
  description = "Version of the Defguard Gateway package to be installed"
  type        = string
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.package_version))
    error_message = "Package version must be in the format X.Y.Z."
  }
}

variable "arch" {
  description = "Architecture of the Defguard Gateway package to be installed"
  type        = string
  validation {
    condition     = contains(["x86_64", "aarch64"], var.arch)
    error_message = "Architecture must be either 'x86_64' or 'aarch64'."
  }
}

variable "nat" {
  description = "Enable masquerading"
  type        = bool
  default     = true
}

variable "log_level" {
  description = "Log level for Defguard Gateway. Possible values: trace, debug, info, warn, error"
  type        = string
  default     = "info"
  validation {
    condition     = contains(["trace", "debug", "info", "warn", "error"], var.log_level)
    error_message = "Log level must be one of: trace, debug, info, warn, error."
  }
}

variable "secrets_manager_arn" {
  description = "ARN of the AWS Secrets Manager secret containing sensitive data"
  type        = string
}

variable "secrets_manager_secret_version" {
  description = "AWS Secrets Manager secret version resource"
  type        = any
}