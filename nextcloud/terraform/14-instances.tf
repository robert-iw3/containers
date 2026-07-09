# Generate the Nextcloud configuration using the template and variable values
locals {
  nextcloud_config = templatefile("${path.root}/templates/nextcloud-docker-swarm.yml.tpl", {
    image_tag           = var.nextcloud_image_tag
    data_storage_path   = var.ebs_volume_1_mount_point
    db_host             = aws_db_instance.db_instance_1.endpoint
    db_name             = var.rds_db_1_name
    redis_host          = aws_elasticache_cluster.redis_1.cache_nodes[0].address
    db_username         = local.rds_db_credentials_1["nextcloud_username"]
    db_password         = local.rds_db_credentials_1["nextcloud_password"]
    admin_user          = local.nextcloud_credentials_1["nextcloud_admin_user"]
    admin_user_password = local.nextcloud_credentials_1["nextcloud_admin_user_password"]
    trusted_domain      = var.nextcloud_trusted_domain
    external_url        = var.nextcloud_external_url
  })
}

# EC2 Instance creation
resource "aws_instance" "instance_1" {
  ami                    = data.aws_ami.ubuntu_24_04.id
  availability_zone      = var.ec2_availability_zone
  subnet_id              = aws_subnet.private_subnet_1a.id
  instance_type          = var.ec2_instance_1_type
  key_name               = aws_key_pair.key_pair_1.key_name
  monitoring             = var.ec2_monitoring
  vpc_security_group_ids = [aws_security_group.ec2_security_group_1.id]

  # Enforcing IMDSv2
  metadata_options {
    http_tokens                 = var.ec2_http_tokens
    http_put_response_hop_limit = var.ec2_http_put_response_hop_limit
    http_endpoint               = var.ec2_http_endpoint
  }

  # Root volume size configuration
  root_block_device {
    volume_size           = var.ec2_root_volume_1_size_gb
    volume_type           = var.ec2_root_volume_1_type
    encrypted             = var.ec2_root_volume_1_encryption
    delete_on_termination = var.ec2_delete_on_termination
  }

  # Generate the user data script using the template and variable values
  user_data = templatefile("${path.root}/templates/user_data.sh.tpl", {
    timestamp                       = timestamp()
    nextcloud_config_file           = local.nextcloud_config
    ebs_volume_1_name               = var.ebs_volume_1_name
    ebs_volume_1_mount_point        = var.ebs_volume_1_mount_point
    backup_ebs_volume_1_name        = var.backup_ebs_volume_1_name
    backup_ebs_volume_1_mount_point = var.backup_ebs_volume_1_mount_point
    db_host_install                 = aws_db_instance.db_instance_1.endpoint
    db_name_install                 = var.rds_db_1_name
    db_username_install             = local.rds_db_credentials_1["nextcloud_username"]
    db_password_install             = local.rds_db_credentials_1["nextcloud_password"]
  })

  lifecycle {
    ignore_changes = [user_data]
  }

  tags = {
    Name = "nextcloud-1"
  }

  depends_on = [
    aws_security_group.ec2_security_group_1,
    tls_private_key.private_key_1,
    aws_key_pair.key_pair_1,
    aws_db_instance.db_instance_1
  ]
}
