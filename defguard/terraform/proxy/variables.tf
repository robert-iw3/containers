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

variable "proxy_url" {
  description = "URL of the Proxy instance"
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

variable "network_interface_id" {
  description = "Network interface ID for the instance"
  type        = string
}

variable "arch" {
  description = "Architecture of the Defguard Proxy package to be installed"
  type        = string
  validation {
    condition     = contains(["x86_64", "aarch64"], var.arch)
    error_message = "Architecture must be either 'x86_64' or 'aarch64'."
  }
}

variable "package_version" {
  description = "Version of the Defguard Proxy package to be installed"
  type        = string
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.package_version))
    error_message = "Package version must be in the format X.Y.Z."
  }
}

variable "http_port" {
  description = "Port to be used to access Defguard Proxy via HTTP"
  type        = number
  default     = 8080
  validation {
    condition     = var.http_port >= 80 && var.http_port <= 65535
    error_message = "HTTP port must be between 80 and 65535."
  }
}

variable "log_level" {
  description = "Log level for Defguard Proxy. Possible values: trace, debug, info, warn, error"
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