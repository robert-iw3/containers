output "vm_ips" {
  value = { for k, v in local.vms : k => v.ip }
}

output "consul_ui" {
  value = "https://${var.consul_ips[0]}:8501/ui"
}

output "vault_addr" {
  value = "https://${var.vault_ips[0]}:8200"
}

output "vault_init_hint" {
  value = "Shamir seal: run `vault operator init` against ${var.vault_ips[0]} after first boot."
}

output "boundary_addr" {
  value = "http://${var.boundary_controller_ip}:9200"
}

output "boundary_admin_credentials_hint" {
  value = "SSH to the controller and read /var/log/boundary-db-init.log for the generated admin credentials."
}

output "consul_gossip_key" {
  value     = random_bytes.consul_gossip.base64
  sensitive = true
}

output "consul_ca_cert" {
  value = module.consul_ca.ca_cert_pem
}

output "vault_ca_cert" {
  value = module.vault_ca.ca_cert_pem
}
