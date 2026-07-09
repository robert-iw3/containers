resource "aws_security_group" "consul_sg" {
  name        = "${var.cluster_name}-consul-sg"
  description = "Security group for Consul cluster"
  vpc_id      = var.vpc_id
  count       = var.consul_enabled ? 1 : 0

  ingress {
    from_port   = 8500
    to_port     = 8503
    protocol    = "tcp"
    cidr_blocks = concat(var.cluster_cidr_blocks, var.admin_cidr_blocks)
    description = "Consul HTTP API/UI + gRPC (Connect) from cluster and operators"
  }
  ingress {
    from_port   = 8300
    to_port     = 8302
    protocol    = "tcp"
    self        = true
    description = "Consul Server RPC + Serf"
  }
  ingress {
    from_port   = 8301
    to_port     = 8302
    protocol    = "udp"
    self        = true
    description = "Consul Serf (UDP)"
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = {
    Name = "${var.cluster_name}-consul-sg"
  }
}

resource "aws_iam_role" "consul_role" {
  name  = "${var.cluster_name}-consul-role"
  count = var.consul_enabled ? 1 : 0
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "consul_policy" {
  name  = "${var.cluster_name}-consul-policy"
  role  = aws_iam_role.consul_role[0].id
  count = var.consul_enabled ? 1 : 0
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeTags"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "consul_profile" {
  name  = "${var.cluster_name}-consul-profile"
  role  = aws_iam_role.consul_role[0].name
  count = var.consul_enabled ? 1 : 0
}

resource "aws_launch_template" "consul_lt" {
  name          = "${var.cluster_name}-consul-lt"
  count         = var.consul_enabled ? 1 : 0
  image_id      = var.ami_id
  instance_type = var.instance_type
  iam_instance_profile {
    name = aws_iam_instance_profile.consul_profile[0].name
  }
  vpc_security_group_ids = [aws_security_group.consul_sg[0].id]
  key_name               = var.ssh_key_name
  user_data = base64encode(templatefile("${path.module}/user-data-consul.sh", {
    cluster_name     = var.cluster_name
    desired_capacity = var.desired_capacity
  }))
  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size = 50
      volume_type = "gp3"
    }
  }
  tag_specifications {
    resource_type = "instance"
    tags = {
      Name           = "${var.cluster_name}-consul"
      ConsulAutoJoin = "auto-join"
    }
  }
}

resource "aws_autoscaling_group" "consul_asg" {
  name                = "${var.cluster_name}-consul-asg"
  desired_capacity    = var.desired_capacity
  max_size            = var.desired_capacity + 1
  min_size            = var.desired_capacity
  vpc_zone_identifier = var.subnet_ids
  count               = var.consul_enabled ? 1 : 0
  launch_template {
    id      = aws_launch_template.consul_lt[0].id
    version = "$Latest"
  }
  health_check_type         = "EC2"
  health_check_grace_period = 300
}