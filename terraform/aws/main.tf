data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  azs         = slice(data.aws_availability_zones.available.names, 0, 3)
  consul_tag  = "${var.name_prefix}-consul-server"
  vault_tag   = "${var.name_prefix}-vault-server"
  common_tags = merge(var.tags, { project = var.name_prefix })
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.common_tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.common_tags, { Name = "${var.name_prefix}-igw" })
}

resource "aws_subnet" "public" {
  count                   = 3
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(local.common_tags, { Name = "${var.name_prefix}-public-${count.index}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(local.common_tags, { Name = "${var.name_prefix}-public" })
}

resource "aws_route_table_association" "public" {
  count          = 3
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "internal" {
  name_prefix = "${var.name_prefix}-internal-"
  description = "Intra-stack traffic"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "all traffic between stack members"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_security_group" "admin" {
  name_prefix = "${var.name_prefix}-admin-"
  description = "Operator access to SSH and product APIs/UIs"
  vpc_id      = aws_vpc.this.id

  dynamic "ingress" {
    for_each = length(var.allowed_admin_cidrs) > 0 ? {
      ssh           = 22
      vault         = 8200
      consul_http   = 8500
      consul_https  = 8501
      boundary_api  = 9200
      boundary_prox = 9202
      boundary_ops  = 9203
    } : {}

    content {
      description = ingress.key
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = var.allowed_admin_cidrs
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# IAM: cloud auto-join + KMS unseal
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "stack" {
  name_prefix        = "${var.name_prefix}-"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "stack" {
  statement {
    sid       = "AutoJoin"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    sid = "KmsSeal"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey",
    ]
    resources = [
      aws_kms_key.vault_unseal.arn,
      aws_kms_key.boundary_root.arn,
      aws_kms_key.boundary_worker_auth.arn,
      aws_kms_key.boundary_recovery.arn,
    ]
  }
}

resource "aws_iam_role_policy" "stack" {
  name_prefix = "${var.name_prefix}-"
  role        = aws_iam_role.stack.id
  policy      = data.aws_iam_policy_document.stack.json
}

resource "aws_iam_instance_profile" "stack" {
  name_prefix = "${var.name_prefix}-"
  role        = aws_iam_role.stack.name
  tags        = local.common_tags
}

# ---------------------------------------------------------------------------
# KMS keys
# ---------------------------------------------------------------------------

resource "aws_kms_key" "vault_unseal" {
  description             = "${var.name_prefix} vault auto-unseal"
  deletion_window_in_days = 7
  tags                    = local.common_tags
}

resource "aws_kms_key" "boundary_root" {
  description             = "${var.name_prefix} boundary root"
  deletion_window_in_days = 7
  tags                    = local.common_tags
}

resource "aws_kms_key" "boundary_worker_auth" {
  description             = "${var.name_prefix} boundary worker-auth"
  deletion_window_in_days = 7
  tags                    = local.common_tags
}

resource "aws_kms_key" "boundary_recovery" {
  description             = "${var.name_prefix} boundary recovery"
  deletion_window_in_days = 7
  tags                    = local.common_tags
}

# ---------------------------------------------------------------------------
# Shared secrets and TLS
# ---------------------------------------------------------------------------

resource "random_bytes" "consul_gossip" {
  length = 32
}

module "consul_ca" {
  source      = "../modules/internal-ca"
  common_name = "server.${var.datacenter}.consul"
  dns_sans    = ["server.${var.datacenter}.consul", "localhost"]
}

module "vault_ca" {
  source      = "../modules/internal-ca"
  common_name = "vault.internal"
  dns_sans    = ["vault.internal", "localhost"]
}

# ---------------------------------------------------------------------------
# Boundary database (RDS PostgreSQL)
# ---------------------------------------------------------------------------

resource "random_password" "boundary_db" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "boundary" {
  name_prefix = "${var.name_prefix}-"
  subnet_ids  = aws_subnet.public[*].id
  tags        = local.common_tags
}

resource "aws_db_instance" "boundary" {
  identifier_prefix      = "${var.name_prefix}-boundary-"
  engine                 = "postgres"
  engine_version         = "17"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  db_name                = "boundary"
  username               = "boundary"
  password               = random_password.boundary_db.result
  db_subnet_group_name   = aws_db_subnet_group.boundary.name
  vpc_security_group_ids = [aws_security_group.internal.id]
  publicly_accessible    = false
  skip_final_snapshot    = true
  apply_immediately      = true
  tags                   = local.common_tags
}

# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

module "consul_userdata" {
  source          = "../modules/hashicorp-install"
  product         = "consul"
  product_version = var.consul_version
  exec_start      = "/usr/local/bin/consul agent -config-dir=/etc/consul.d"
  config          = local.consul_config

  extra_files = {
    "/etc/consul.d/tls/ca.pem"   = module.consul_ca.ca_cert_pem
    "/etc/consul.d/tls/cert.pem" = module.consul_ca.cert_pem
    "/etc/consul.d/tls/key.pem"  = module.consul_ca.key_pem
  }
}

resource "aws_instance" "consul" {
  count                  = var.consul_servers
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type["consul"]
  subnet_id              = aws_subnet.public[count.index % 3].id
  vpc_security_group_ids = [aws_security_group.internal.id, aws_security_group.admin.id]
  iam_instance_profile   = aws_iam_instance_profile.stack.name
  key_name               = var.key_name
  user_data              = module.consul_userdata.user_data

  metadata_options {
    http_tokens = "required"
  }

  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-consul-${count.index}"
    role = local.consul_tag
  })
}

module "vault_userdata" {
  source          = "../modules/hashicorp-install"
  product         = "vault"
  product_version = var.vault_version
  exec_start      = "/usr/local/bin/vault server -config=/etc/vault.d/server.hcl"
  config          = local.vault_config

  extra_files = {
    "/etc/vault.d/tls/ca.pem"   = module.vault_ca.ca_cert_pem
    "/etc/vault.d/tls/cert.pem" = module.vault_ca.cert_pem
    "/etc/vault.d/tls/key.pem"  = module.vault_ca.key_pem
  }
}

resource "aws_instance" "vault" {
  count                  = var.vault_servers
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type["vault"]
  subnet_id              = aws_subnet.public[count.index % 3].id
  vpc_security_group_ids = [aws_security_group.internal.id, aws_security_group.admin.id]
  iam_instance_profile   = aws_iam_instance_profile.stack.name
  key_name               = var.key_name
  user_data              = module.vault_userdata.user_data

  metadata_options {
    http_tokens = "required"
  }

  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-vault-${count.index}"
    role = local.vault_tag
  })
}

module "boundary_controller_userdata" {
  source          = "../modules/hashicorp-install"
  product         = "boundary"
  product_version = var.boundary_version
  exec_start      = "/usr/local/bin/boundary server -config=/etc/boundary.d/server.hcl"
  config          = local.boundary_controller_config
  env_content     = "BOUNDARY_POSTGRES_URL=postgresql://boundary:${random_password.boundary_db.result}@${aws_db_instance.boundary.endpoint}/boundary"

  extra_setup = <<-EOT
    set -a; . /etc/boundary.d/boundary.env; set +a
    sudo -E -u boundary /usr/local/bin/boundary database init \
      -config /etc/boundary.d/server.hcl > /var/log/boundary-db-init.log 2>&1 \
      || grep -qi 'already.*initialized' /var/log/boundary-db-init.log
    chmod 0600 /var/log/boundary-db-init.log
  EOT
}

resource "aws_instance" "boundary_controller" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type["boundary"]
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.internal.id, aws_security_group.admin.id]
  iam_instance_profile   = aws_iam_instance_profile.stack.name
  key_name               = var.key_name
  user_data              = module.boundary_controller_userdata.user_data

  metadata_options {
    http_tokens = "required"
  }

  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-boundary-controller"
    role = "${var.name_prefix}-boundary-controller"
  })
}

module "boundary_worker_userdata" {
  source          = "../modules/hashicorp-install"
  product         = "boundary"
  product_version = var.boundary_version
  exec_start      = "/usr/local/bin/boundary server -config=/etc/boundary.d/server.hcl"
  config          = local.boundary_worker_config
}

resource "aws_instance" "boundary_worker" {
  count                  = var.boundary_workers
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type["boundary"]
  subnet_id              = aws_subnet.public[count.index % 3].id
  vpc_security_group_ids = [aws_security_group.internal.id, aws_security_group.admin.id]
  iam_instance_profile   = aws_iam_instance_profile.stack.name
  key_name               = var.key_name
  user_data              = module.boundary_worker_userdata.user_data

  metadata_options {
    http_tokens = "required"
  }

  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-boundary-worker-${count.index}"
    role = "${var.name_prefix}-boundary-worker"
  })
}
