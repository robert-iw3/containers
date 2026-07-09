output "bucket_1_name" {
  description = "The name of the S3 bucket that is being used to store the Terraform state file"
  value       = aws_s3_bucket.bucket_1.bucket
}

output "log_bucket_1_name" {
  description = "The name of the S3 bucket that is being used to store the Terraform state file"
  value       = aws_s3_bucket.log_bucket_1.bucket
}

output "nextcloud_external_url" {
  description = "URL on which Nextcloud will be reachable"
  value       = var.nextcloud_external_url
}

output "rds_1_address" {
  description = "The address of the RDS instance"
  value       = aws_db_instance.db_instance_1.endpoint
}

output "redis_1_address" {
  description = "The address of the Redis node"
  value       = aws_elasticache_cluster.redis_1.cache_nodes[0].address
}

output "alb_1_dns_name" {
  description = "The address of the load balancer"
  value       = aws_lb.alb_1.dns_name
}
