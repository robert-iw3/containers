# Configuring the AWS provider
provider "aws" {
  region     = local.region
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
}

# Fetching the latest Ubuntu AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# Generating a random password for the gateway secret
resource "random_password" "gateway_secret" {
  length  = 64
  special = false
}

# Storing sensitive data in AWS Secrets Manager
resource "aws_secretsmanager_secret" "defguard_secrets" {
  name = "defguard-secrets-${random_id.secret_suffix.hex}"
}

resource "aws_secretsmanager_secret_version" "defguard_secrets_version" {
  secret_id = aws_secretsmanager_secret.defguard_secrets.id
  secret_string = jsonencode({
    db_password            = local.db_password
    gateway_secret         = random_password.gateway_secret.result
    default_admin_password = local.default_admin_password
  })
}

resource "random_id" "secret_suffix" {
  byte_length = 8
}

# Defguard Core instance configuration
resource "aws_instance" "defguard_core" {
  ami           = var.ami
  instance_type = var.instance_type

  user_data = templatefile("${path.module}/setup.py", {
    db_address             = var.db_details.address
    db_name                = var.db_details.name
    db_username            = var.db_details.username
    db_port                = var.db_details.port
    core_url               = var.core_url
    proxy_address          = var.proxy_address
    proxy_grpc_port        = var.proxy_grpc_port
    proxy_url              = var.proxy_url
    grpc_port              = var.grpc_port
    http_port              = var.http_port
    package_version        = var.package_version
    arch                   = var.arch
    cookie_insecure        = var.cookie_insecure
    log_level              = var.log_level
    secrets_manager_arn    = aws_secretsmanager_secret.defguard_secrets.arn
  })
  user_data_replace_on_change = true

  primary_network_interface {
    network_interface_id = var.network_interface_id
  }

  tags = {
    Name = "defguard-core-instance"
  }

  depends_on = [aws_secretsmanager_secret_version.defguard_secrets_version]
}

# VPC configuration
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name            = local.vpc_name
  cidr            = local.vpc_cidr
  azs             = local.azs
  private_subnets = local.vpc_private_subnets
  public_subnets  = local.vpc_public_subnets

  enable_dns_hostnames = true
  tags                 = local.vpc_tags
}

# Core database configuration
resource "aws_db_instance" "defguard_core_db" {
  engine                 = "postgres"
  instance_class         = local.db_instance_class
  username               = local.db_username
  password               = local.db_password
  db_name                = local.db_name
  port                   = local.db_port
  skip_final_snapshot    = true
  allocated_storage      = local.db_storage
  db_subnet_group_name   = aws_db_subnet_group.defguard.name
  vpc_security_group_ids = [aws_security_group.defguard_db_sg.id]
  parameter_group_name   = aws_db_parameter_group.defguard_db_parameter_group.name
}

resource "aws_db_parameter_group" "defguard_db_parameter_group" {
  name   = "defguard-db-parameter-group"
  family = "postgres17"

  parameter {
    name  = "rds.force_ssl"
    value = "0"
  }
}

resource "aws_db_subnet_group" "defguard" {
  name       = "defguard-db-subnet-group"
  subnet_ids = module.vpc.private_subnets
}

# Core network configuration
resource "aws_eip" "defguard_core_endpoint" {
  domain = "vpc"
}

resource "aws_eip_association" "defguard_core_endpoint_association" {
  network_interface_id = aws_network_interface.defguard_core_network_interface.id
  allocation_id        = aws_eip.defguard_core_endpoint.id
}

resource "aws_security_group" "defguard_core_sg" {
  name        = "defguard-core-sg"
  description = "Security group for Defguard Core"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = local.core_http_port
    to_port     = local.core_http_port
    protocol    = "tcp"
    cidr_blocks = [for eip in aws_eip.defguard_gateway_endpoint : "${eip.public_ip}/32"]
  }

  ingress {
    from_port       = local.core_grpc_port
    to_port         = local.core_grpc_port
    protocol        = "tcp"
    security_groups = [for sg in aws_security_group.defguard_gateway_sg : sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_network_interface" "defguard_core_network_interface" {
  subnet_id       = module.vpc.public_subnets[0]
  security_groups = [aws_security_group.defguard_core_sg.id]

  tags = {
    Name = "defguard-core-network-interface"
  }
}

# Gateway network configuration
resource "aws_eip" "defguard_gateway_endpoint" {
  count  = length(local.vpn_networks)
  domain = "vpc"
}

resource "aws_eip_association" "defguard_gateway_endpoint_association" {
  count                = length(local.vpn_networks)
  network_interface_id = aws_network_interface.defguard_gateway_network_interface[count.index].id
  allocation_id        = aws_eip.defguard_gateway_endpoint[count.index].id
}

resource "aws_security_group" "defguard_gateway_sg" {
  count       = length(local.vpn_networks)
  name        = "defguard-gateway-sg-${count.index}"
  description = "Security group for Defguard Gateway ${count.index}"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = local.vpn_networks[count.index].port
    to_port     = local.vpn_networks[count.index].port
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_network_interface" "defguard_gateway_network_interface" {
  count           = length(local.vpn_networks)
  subnet_id       = module.vpc.public_subnets[0]
  security_groups = [aws_security_group.defguard_gateway_sg[count.index].id]

  tags = {
    Name = "defguard-gateway-network-interface-${count.index}"
  }
}

# Proxy network configuration
resource "aws_eip" "defguard_proxy_endpoint" {
  domain = "vpc"
}

resource "aws_eip_association" "defguard_proxy_endpoint_association" {
  network_interface_id = aws_network_interface.defguard_proxy_network_interface.id
  allocation_id        = aws_eip.defguard_proxy_endpoint.id
}

resource "aws_security_group" "defguard_proxy_sg" {
  name        = "defguard-proxy-sg"
  description = "Security group for Defguard Proxy"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = local.proxy_http_port
    to_port     = local.proxy_http_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port       = local.proxy_grpc_port
    to_port         = local.proxy_grpc_port
    protocol        = "tcp"
    security_groups = [aws_security_group.defguard_core_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_network_interface" "defguard_proxy_network_interface" {
  subnet_id       = module.vpc.public_subnets[0]
  security_groups = [aws_security_group.defguard_proxy_sg.id]

  tags = {
    Name = "defguard-proxy-network-interface"
  }
}

# Database network configuration
resource "aws_security_group" "defguard_db_sg" {
  name        = "defguard-db-sg"
  description = "Security group for Defguard database"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = local.db_port
    to_port         = local.db_port
    protocol        = "tcp"
    security_groups = [aws_security_group.defguard_core_sg.id]
  }

  tags = {
    Name = "defguard-db-sg"
  }
}

# Defguard Core module
module "defguard_core" {
  source          = "github.com/DefGuard/deployment//terraform/modules/core?ref=main"
  instance_type   = local.core_instance_type
  package_version = local.core_package_version
  arch            = local.core_arch
  ami             = data.aws_ami.ubuntu.id

  core_url        = local.core_url
  proxy_grpc_port = local.proxy_grpc_port
  proxy_url       = local.proxy_url
  grpc_port       = local.core_grpc_port
  http_port       = local.core_http_port
  cookie_insecure = local.core_cookie_insecure
  vpn_networks = [for network in local.vpn_networks : {
    id       = network.id
    name     = network.name
    address  = network.address
    port     = network.port
    endpoint = aws_eip.defguard_gateway_endpoint[network.id - 1].public_ip
  }]
  db_details = {
    name     = local.db_name
    username = local.db_username
    password = local.db_password
    port     = local.db_port
    address  = aws_db_instance.defguard_core_db.address
  }
  proxy_address        = module.defguard_proxy.proxy_private_address
  gateway_secret       = random_password.gateway_secret.result
  network_interface_id = aws_network_interface.defguard_core_network_interface.id
}

# Defguard Proxy module
module "defguard_proxy" {
  source = "github.com/DefGuard/deployment//terraform/modules/proxy?ref=main"

  instance_type   = local.proxy_instance_type
  package_version = local.proxy_package_version
  arch            = local.proxy_arch
  grpc_port       = local.proxy_grpc_port
  http_port       = local.proxy_http_port
  proxy_url       = local.proxy_url
  ami             = data.aws_ami.ubuntu.id
  network_interface_id = aws_network_interface.defguard_proxy_network_interface.id
}

# Defguard Gateway module
module "defguard_gateway" {
  count = length(local.vpn_networks)
  source = "github.com/DefGuard/deployment//terraform/modules/gateway?ref=main"

  ami             = data.aws_ami.ubuntu.id
  instance_type   = local.gateway_instance_type
  package_version = local.gateway_package_version
  arch            = local.gateway_arch
  core_grpc_port  = local.core_grpc_port
  nat             = local.vpn_networks[count.index].nat
  network_id      = local.vpn_networks[count.index].id
  gateway_secret  = random_password.gateway_secret.result
  network_interface_id = aws_network_interface.defguard_gateway_network_interface[count.index].id
  core_address    = aws_network_interface.defguard_core_network_interface.private_ip

  depends_on = [module.defguard_core]
}