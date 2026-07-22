output "instance_id" {
  description = "ID of the Defguard Gateway instance"
  value       = aws_instance.defguard_gateway.id
}

output "gateway_private_address" {
  description = "Private IP address of the Defguard Gateway instance"
  value       = var.network_interface_id != "" ? data.aws_network_interface.gateway.private_ip : null
}

output "gateway_public_address" {
  description = "Public IP address of the Defguard Gateway instance (if associated)"
  value       = var.network_interface_id != "" ? data.aws_eip_association.gateway.public_ip : null
}

data "aws_network_interface" "gateway" {
  id = var.network_interface_id
}

data "aws_eip_association" "gateway" {
  count         = var.network_interface_id != "" ? 1 : 0
  allocation_id = var.network_interface_id
}