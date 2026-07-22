terraform {
    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.31.0"
        }
    }
    required_version = ">=4.4.0"
}