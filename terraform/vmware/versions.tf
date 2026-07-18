terraform {
  required_version = ">= 1.9.0"

  required_providers {
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

# credentials via TF_VAR_vsphere_server / TF_VAR_vsphere_user /
# TF_VAR_vsphere_password (or terraform.tfvars — avoid committing secrets)
provider "vsphere" {
  vsphere_server       = var.vsphere_server
  user                 = var.vsphere_user
  password             = var.vsphere_password
  allow_unverified_ssl = var.allow_unverified_ssl
}
