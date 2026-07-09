variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "deployment_type" {
  description = "Deployment type: 'aws' or 'bare_metal'"
  type        = string
  default     = "bare_metal"
}

variable "instance_type" {
  description = "EC2 instance type for Splunk"
  type        = string
  default     = "t3.medium"
}

variable "indexing_volume" {
  description = "Indexing volume in GB"
  type        = number
  default     = 100
}

variable "allowed_cidr" {
  description = "CIDR block allowed to access Splunk"
  type        = string
  default     = "0.0.0.0/0"
}

variable "secrets_id" {
  description = "AWS Secrets Manager secret ID for Splunk credentials"
  type        = string
  default     = ""
}