variable "deployment_type" {
  description = "Deployment type: 'aws' or 'bare_metal'"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for Splunk"
  type        = string
}

variable "indexing_volume" {
  description = "Indexing volume in GB"
  type        = number
}

variable "allowed_cidr" {
  description = "CIDR block allowed to access Splunk"
  type        = string
}

variable "secrets_id" {
  description = "AWS Secrets Manager secret ID for Splunk credentials"
  type        = string
}