locals {
  # this local var is used to whitelist inbound ssh connections
  allow-ips = [
    "this.ip.right.here/32",
    "this.ip.right.here/32",
    "this.ip.right.here/32",
    "10.1.1.0/24"
  ]
}

resource "aws_security_group" "sonarqube-sg" {
  name        = "sonarqube-sg"
  description = "Sonarqube Instance Security Group"
  vpc_id      = aws_vpc.__________________________.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = local.allow-ips
  }

  ingress {
    from_port   = 9000
    to_port     = 9000
    protocol    = "tcp"
    cidr_blocks = local.allow-ips
  }

  ingress {
    from_port       = 9000
    to_port         = 9000
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
    Name      = "Sonarqube Scanning Instance"
    ManagedBy = "terraform"
  }
}

resource "aws_security_group" "sonarqube-alb-sg" {
  name        = "sonarqube-alb-sg"
  description = "ALB Security Group for Sonarqube"
  vpc_id      = aws_vpc.__________________________.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = local.allow-ips
  }

  ingress {
    from_port   = 9000
    to_port     = 9000
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
    Name      = "ALB for Sonarqube Scanning Instance"
    ManagedBy = "terraform"
  }
}

resource "aws_vpc" "dev-sonarqube" {
  cidr_block = "my_subnet/16"

  tags = {
    Name      = "Dev Sonarqube VPC"
    ManagedBy = "terraform"
  }
}

resource "aws_internet_gateway" "dev-sonarqube-igw" {
  vpc_id = aws_vpc.______________.id

  tags = {
    Name      = "Dev Sonarqube Internet Gateway"
    ManagedBy = "terraform"
  }
}

resource "aws_subnet" "dev-sonarqube-subnet" {
  vpc_id                  = aws_vpc.__________________________.id
  cidr_block              = "my_subnet/24"
  availability_zone       = "us-west-2a"
  map_public_ip_on_launch = true

  tags = {
    Name      = "Dev Sonarqube Subnet in Some AZ"
    ManagedBy = "terraform"
  }
}

# ALB requires two subnets in different AZs, so we create this
# subnet just for it
resource "aws_subnet" "dev-sonarqube-subnet-b" {
  vpc_id                  = aws_vpc.__________________________.id
  cidr_block              = "my_subnet/24"
  availability_zone       = "us-west-2b"
  map_public_ip_on_launch = true

  tags = {
    Name      = "Dev Sonarqube Subnet in Denver AZ b"
    ManagedBy = "terraform"
  }
}

resource "aws_route_table" "dev-sonarqube-route-table" {
  vpc_id = aws_vpc.__________________________.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.dev-sonarqube-igw.id
  }

  tags = {
    Name      = "Dev Sonarqube Routing Table"
    ManagedBy = "terraform"
  }
}

resource "aws_route_table_association" "dev-sonarqube-association" {
  subnet_id      = aws_subnet.__________________________.id
  route_table_id = aws_route_table.__________________________.id
}

resource "aws_route_table_association" "dev-sonarqube-association-b" {
  subnet_id      = aws_subnet.__________________________.id
  route_table_id = aws_route_table.__________________________.id
}
