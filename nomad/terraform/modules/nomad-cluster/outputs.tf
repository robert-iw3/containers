output "security_group_id" {
  description = "Security group ID for Nomad cluster"
  value       = aws_security_group.nomad_sg.id
}

output "instance_ips" {
  description = "Private IPs of Nomad instances"
  value       = data.aws_instances.nomad_instances.private_ips
}

output "asg_name" {
  description = "Name of the Nomad autoscaling group"
  value       = aws_autoscaling_group.nomad_asg.name
}