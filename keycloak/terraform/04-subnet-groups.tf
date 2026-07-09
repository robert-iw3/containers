# RDS Subnet Group
resource "aws_db_subnet_group" "rds_subnet_group_1" {
  name = var.subnet_group_1_name

  subnet_ids = [
    aws_subnet.private_subnet_1a.id,
    aws_subnet.private_subnet_1b.id,
    aws_subnet.private_subnet_1c.id
  ]

  tags = {
    Name = "rds-subnet-group-keycloak-1"
  }

  depends_on = [
    aws_subnet.private_subnet_1a,
    aws_subnet.private_subnet_1b,
    aws_subnet.private_subnet_1c
  ]
}
