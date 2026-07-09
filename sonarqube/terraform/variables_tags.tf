variable "Service" {
  description = "Service Name"
  type        = string
  default     = "Sonarqube"
}

variable "SvcOwner" {
  description = "Service Owner"
  type        = string
  default     = "The Cybers"
}

variable "Environment" {
  description = "Service Environment"
  type        = string
  default     = "dev"
}

variable "DeployedUsing" {
  description = "Deployed Using"
  type        = string
  default     = "Terraform"
}

variable "SvcCodeURL" {
  description = "Service Code URL"
  type        = string
  default     = "tbd"
}
