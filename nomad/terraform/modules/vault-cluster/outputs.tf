output "security_group_id" {
  description = "Security group ID for Vault cluster"
  value       = var.vault_enabled ? aws_security_group.vault_sg[0].id : ""
}

output "instance_ips" {
  description = "Private IPs of Vault instances"
  value       = var.vault_enabled ? data.aws_instances.vault_instances[0].private_ips : []
}

data "aws_instances" "vault_instances" {
  count = var.vault_enabled ? 1 : 0
  instance_tags = {
    Name = "${var.cluster_name}-vault"
  }
  depends_on = [aws_autoscaling_group.vault_asg]
}
output "vault_address" {
  description = "Internal NLB address for the Vault API"
  value       = var.vault_enabled ? "https://${aws_lb.vault_nlb[0].dns_name}:8200" : ""
}
