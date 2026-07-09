locals {
  # this local var is used to whitelist inbound ssh connections
  allow-ips = [
    "this.ip.right.here/32",
    "this.ip.right.here/32",
    "this.ip.right.here/32",
    "10.1.1.0/24"
  ]
}

resource "aws_security_group" "nessus-sg" {
  name        = "nessus-sg"
  description = "Nessus Instance Security Group"
  vpc_id      = aws_vpc.__________________________.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = local.allow-ips
  }

  ingress {
    from_port   = 8834
    to_port     = 8834
    protocol    = "tcp"
    cidr_blocks = local.allow-ips
  }

  ingress {
    from_port       = 8834
    to_port         = 8834
    protocol        = "tcp"
    security_groups = [aws_security_group.__________________________.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = -1
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name      = "Nessus Scanning Instance"
    ManagedBy = "terraform"
  }
}

resource "aws_security_group" "nessus-alb-sg" {
  name        = "nessus-alb-sg"
  description = "ALB Security Group for Nessus"
  vpc_id      = aws_vpc.__________________________.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = local.allow-ips
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = local.allow-ips
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = -1
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name      = "ALB for Nessus Scanning Instance"
    ManagedBy = "terraform"
  }
}

resource "aws_vpc" "cyber-security-nessus" {
  cidr_block = "my_subnet/16"

  tags = {
    Name      = "Cyber Security Nessus VPC"
    ManagedBy = "terraform"
  }
}

resource "aws_internet_gateway" "cyber-security-nessus-igw" {
  vpc_id = aws_vpc.______________.id

  tags = {
    Name      = "Cyber Security Nessus Internet Gateway"
    ManagedBy = "terraform"
  }
}

resource "aws_subnet" "cyber-security-nessus-subnet" {
  vpc_id                  = aws_vpc.__________________________.id
  cidr_block              = "my_subnet/24"
  availability_zone       = "us-west-2a"
  map_public_ip_on_launch = true

  tags = {
    Name      = "Cyber Security Nessus Subnet in London AZ a"
    ManagedBy = "terraform"
  }
}

# ALB requires two subnets in different AZs, so we create this
# subnet just for it
resource "aws_subnet" "cyber-security-nessus-subnet-b" {
  vpc_id                  = aws_vpc.__________________________.id
  cidr_block              = "my_subnet/24"
  availability_zone       = "us-west-2b"
  map_public_ip_on_launch = true

  tags = {
    Name      = "Cyber Security Nessus Subnet in Denver AZ b"
    ManagedBy = "terraform"
  }
}

resource "aws_route_table" "cyber-security-nessus-route-table" {
  vpc_id = aws_vpc.__________________________.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.cyber-security-nessus-igw.id
  }

  tags = {
    Name      = "Cyber Security Nessus Routing Table"
    ManagedBy = "terraform"
  }
}

resource "aws_route_table_association" "cyber-security-nessus-association" {
  subnet_id      = aws_subnet.__________________________.id
  route_table_id = aws_route_table.__________________________.id
}

resource "aws_route_table_association" "cyber-security-nessus-association-b" {
  subnet_id      = aws_subnet.__________________________.id
  route_table_id = aws_route_table.__________________________.id
}
