terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket         = "splunk-terraform-state"
    key            = "splunk/state.tfstate"
    region         = "us-east-1"
    dynamodb_table = "splunk-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

module "splunk_instance" {
  source         = "./modules/splunk_instance"
  deployment_type = var.deployment_type
  instance_type  = var.instance_type
  indexing_volume = var.indexing_volume
  allowed_cidr   = var.allowed_cidr
  secrets_id     = var.secrets_id
}