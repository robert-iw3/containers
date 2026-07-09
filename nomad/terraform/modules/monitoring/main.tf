resource "aws_iam_role" "monitoring_role" {
  name = "${var.cluster_name}-monitoring-role"
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

resource "aws_iam_role_policy" "monitoring_policy" {
  name = "${var.cluster_name}-monitoring-policy"
  role = aws_iam_role.monitoring_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = var.secrets_arn
      },
      {
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "monitoring_profile" {
  name = "${var.cluster_name}-monitoring-profile"
  role = aws_iam_role.monitoring_role.name
}

resource "aws_instance" "monitoring" {
  ami                    = var.monitoring_ami_id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_ids[0]
  key_name               = var.ssh_key_name
  iam_instance_profile   = aws_iam_instance_profile.monitoring_profile.name
  vpc_security_group_ids = [aws_security_group.monitoring_sg.id]

  user_data = templatefile("${path.module}/user-data-monitoring.sh", {
    prometheus_config = base64encode(templatefile("${path.module}/prometheus.yml", {
      nomad_ips  = var.nomad_ips,
      consul_ips = var.consul_ips,
      vault_ips  = var.vault_ips
    })),
    secrets_arn = var.secrets_arn,
    aws_region  = var.aws_region
  })

  tags = {
    Name = "${var.cluster_name}-monitoring"
  }
}

resource "aws_security_group" "monitoring_sg" {
  name_prefix = "${var.cluster_name}-monitoring-"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = length(var.admin_cidr_blocks) > 0 ? [9090, 3000, 443] : []
    content {
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = var.admin_cidr_blocks
      description = "Prometheus/Grafana/ALB (operators)"
    }
  }

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    self        = true
    description = "ALB to Grafana target"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "grafana_lb" {
  name               = "${var.cluster_name}-grafana-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.monitoring_sg.id]
  subnets            = var.subnet_ids
}

resource "aws_lb_target_group" "grafana_tg" {
  name     = "${var.cluster_name}-grafana-tg"
  port     = 3000
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    path                = "/api/health"
    protocol            = "HTTP"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "grafana_listener" {
  load_balancer_arn = aws_lb.grafana_lb.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.ssl_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.grafana_tg.arn
  }
}

resource "aws_lb_target_group_attachment" "grafana_attachment" {
  target_group_arn = aws_lb_target_group.grafana_tg.arn
  target_id        = aws_instance.monitoring.id
  port             = 3000
}

output "monitoring_instance_ip" {
  description = "Private IP of the monitoring instance"
  value       = aws_instance.monitoring.private_ip
}

output "grafana_lb_address" {
  description = "DNS name of the Grafana load balancer"
  value       = aws_lb.grafana_lb.dns_name
}