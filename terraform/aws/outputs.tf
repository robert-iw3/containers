output "consul_public_ips" {
  value = aws_instance.consul[*].public_ip
}

output "consul_ui" {
  value = "https://${aws_instance.consul[0].public_ip}:8501/ui"
}

output "vault_public_ips" {
  value = aws_instance.vault[*].public_ip
}

output "vault_addr" {
  value = "https://${aws_instance.vault[0].public_ip}:8200"
}

output "boundary_controller_public_ip" {
  value = aws_instance.boundary_controller.public_ip
}

output "boundary_addr" {
  value = "http://${aws_instance.boundary_controller.public_ip}:9200"
}

output "boundary_worker_public_ips" {
  value = aws_instance.boundary_worker[*].public_ip
}

output "boundary_db_endpoint" {
  value = aws_db_instance.boundary.endpoint
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
