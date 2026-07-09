output "security_group_id" {
  description = "Security group ID for Consul cluster"
  value       = var.consul_enabled ? aws_security_group.consul_sg[0].id : ""
}

output "instance_ips" {
  description = "Private IPs of Consul instances"
  value       = var.consul_enabled ? data.aws_instances.consul_instances[0].private_ips : []
}

data "aws_instances" "consul_instances" {
  count = var.consul_enabled ? 1 : 0
  instance_tags = {
    Name = "${var.cluster_name}-consul"
  }
  depends_on = [aws_autoscaling_group.consul_asg]
}