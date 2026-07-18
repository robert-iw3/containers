output "vm_public_ips" {
  value = { for k, v in azurerm_public_ip.vm : k => v.ip_address }
}

output "consul_ui" {
  value = "https://${azurerm_public_ip.vm["consul-0"].ip_address}:8501/ui"
}

output "vault_addr" {
  value = "https://${azurerm_public_ip.vm["vault-0"].ip_address}:8200"
}

output "boundary_addr" {
  value = "http://${azurerm_public_ip.vm["boundary-controller"].ip_address}:9200"
}

output "boundary_db_fqdn" {
  value = azurerm_postgresql_flexible_server.boundary.fqdn
}

output "boundary_admin_credentials_hint" {
  value = "SSH to the controller and read /var/log/boundary-db-init.log for the generated admin credentials."
}

output "key_vault_name" {
  value = azurerm_key_vault.this.name
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
