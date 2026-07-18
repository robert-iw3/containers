output "ca_cert_pem" {
  value = tls_self_signed_cert.ca.cert_pem
}

output "cert_pem" {
  value = tls_locally_signed_cert.leaf.cert_pem
}

output "key_pem" {
  value     = tls_private_key.leaf.private_key_pem
  sensitive = true
}
