terraform {
  required_version = ">= 1.5.0"
  required_providers {
    tls = {
      source  = "hashicorp/tls"
      version = ">= 4.0"
    }
  }
}

resource "tls_private_key" "ca" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P384"
}

resource "tls_self_signed_cert" "ca" {
  private_key_pem = tls_private_key.ca.private_key_pem

  subject {
    common_name  = "${var.common_name} internal CA"
    organization = var.organization
  }

  validity_period_hours = var.ca_validity_hours
  is_ca_certificate     = true
  allowed_uses          = ["cert_signing", "crl_signing", "digital_signature"]
}

resource "tls_private_key" "leaf" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P384"
}

resource "tls_cert_request" "leaf" {
  private_key_pem = tls_private_key.leaf.private_key_pem

  subject {
    common_name  = var.common_name
    organization = var.organization
  }

  dns_names    = var.dns_sans
  ip_addresses = var.ip_sans
}

resource "tls_locally_signed_cert" "leaf" {
  cert_request_pem      = tls_cert_request.leaf.cert_request_pem
  ca_private_key_pem    = tls_private_key.ca.private_key_pem
  ca_cert_pem           = tls_self_signed_cert.ca.cert_pem
  validity_period_hours = var.leaf_validity_hours

  allowed_uses = ["key_encipherment", "digital_signature", "server_auth", "client_auth"]
}
