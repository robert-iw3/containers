output "instance_public_ips" {
  value = { for k, v in google_compute_instance.vm : k => v.network_interface[0].access_config[0].nat_ip }
}

output "consul_ui" {
  value = "https://${google_compute_instance.vm["consul-0"].network_interface[0].access_config[0].nat_ip}:8501/ui"
}

output "vault_addr" {
  value = "https://${google_compute_instance.vm["vault-0"].network_interface[0].access_config[0].nat_ip}:8200"
}

output "boundary_addr" {
  value = "http://${google_compute_instance.vm["boundary-controller"].network_interface[0].access_config[0].nat_ip}:9200"
}

output "boundary_db_private_ip" {
  value = google_sql_database_instance.boundary.private_ip_address
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
