variable "cluster_name" {
  description = "Name prefix for VPC resources"
  type        = string
}

variable "aws_region" {
  description = "AWS region this VPC is created in"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidrs" {
  description = "CIDR blocks for the public subnets, one per availability zone"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}
