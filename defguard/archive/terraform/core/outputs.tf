output "instance_id" {
  description = "ID of Defguard Core instance"
  value       = aws_instance.defguard_core.id
}

output "defguard_core_private_address" {
  description = "IP address of Defguard Core instance in the internal network"
  value       = aws_network_interface.defguard_core_network_interface.private_ip
}

output "defguard_core_public_address" {
  description = "Public IP address of Defguard Core instance"
  value       = aws_eip.defguard_core_endpoint.public_ip
}

output "defguard_proxy_public_address" {
  description = "Public IP address of Defguard Proxy instance"
  value       = aws_eip.defguard_proxy_endpoint.public_ip
}

output "defguard_proxy_private_address" {
  description = "Private IP address of Defguard Proxy instance"
  value       = aws_network_interface.defguard_proxy_network_interface.private_ip
}

output "defguard_gateway_public_addresses" {
  description = "Public IP addresses of Defguard Gateway instances"
  value       = [for gw in aws_eip.defguard_gateway_endpoint : gw.public_ip]
}

output "defguard_gateway_private_addresses" {
  description = "Private IP addresses of Defguard Gateway instances"
  value       = [for gw in aws_network_interface.defguard_gateway_network_interface : gw.private_ip]
}

output "secrets_manager_arn" {
  description = "ARN of the AWS Secrets Manager secret containing sensitive data"
  value       = aws_secretsmanager_secret.defguard_secrets.arn
}