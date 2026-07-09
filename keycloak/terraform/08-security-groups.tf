# Security group creation
resource "aws_security_group" "rds_security_group_1" {
  vpc_id = aws_vpc.vpc_1.id

  name        = "rds-security-group-keycloak-1"
  description = "RDS Security Group Keycloak 1"

  # Inbound port configuration
  ingress {
    description     = "Allow inbound traffic on port 5432 for PostgreSQL"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_security_group_1.id]
  }

  # Outbound port configuration
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    #tfsec:ignore:aws-vpc-no-public-egress-sgr
    cidr_blocks = ["0.0.0.0/0"]
  }

  depends_on = [aws_vpc.vpc_1]
}

# Security group creation
resource "aws_security_group" "ec2_security_group_1" {
  vpc_id = aws_vpc.vpc_1.id

  name        = "instance-security-group-keycloak-1"
  description = "Instance Security Group Keycloak 1"

  # Inbound port configuration for ALB on port 8080
  ingress {
    description     = "Allow inbound HTTP traffic from ALB security group"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_1_security_group_1.id]
  }

  # Inbound port configuration for ALB on port 443
  ingress {
    description     = "Allow inbound HTTPS traffic from ALB security group"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_1_security_group_1.id]
  }

  # Inbound port configuration for ALB on port 9000
  ingress {
    description     = "Allow inbound healthcheck traffic from ALB security group"
    from_port       = 9000
    to_port         = 9000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_1_security_group_1.id]
  }

  # Inbound port configuration
  ingress {
    description = "Allow inbound SSH traffic"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    #tfsec:ignore:aws-ec2-no-public-ingress-sgr
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound port configuration
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    #tfsec:ignore:aws-ec2-no-public-egress-sgr
    cidr_blocks = ["0.0.0.0/0"]
  }

  depends_on = [aws_vpc.vpc_1]
}

resource "aws_security_group" "alb_1_security_group_1" {
  vpc_id = aws_vpc.vpc_1.id

  name        = "application-load-balancer-1-keycloak-1"
  description = "Allow inbound traffic for the load balancer"

  # Inbound port configuration
  ingress {
    description = "Allow inbound HTTP traffic"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    #tfsec:ignore:aws-ec2-no-public-ingress-sgr
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Inbound port configuration
  ingress {
    description = "Allow inbound HTTPS traffic"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    #tfsec:ignore:aws-ec2-no-public-ingress-sgr
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound port configuration
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    #tfsec:ignore:aws-ec2-no-public-egress-sgr
    cidr_blocks = ["0.0.0.0/0"]
  }
}
