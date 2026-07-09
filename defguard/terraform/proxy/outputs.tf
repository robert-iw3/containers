output "proxy_private_address" {
  description = "Private IP address of Defguard Proxy instance"
  value       = var.network_interface_id != "" ? data.aws_network_interface.proxy.private_ip : null
}

output "proxy_public_address" {
  description = "Public IP address of Defguard Proxy instance (if associated)"
  value       = var.network_interface_id != "" ? data.aws_eip_association.proxy.public_ip : null
}

output "instance_id" {
  description = "ID of Defguard Proxy instance"
  value       = aws_instance.defguard_proxy.id
}

data "aws_network_interface" "proxy" {
  id = var.network_interface_id
}

data "aws_eip_association" "proxy" {
  count         = var.network_interface_id != "" ? 1 : 0
  allocation_id = var.network_interface_id
}