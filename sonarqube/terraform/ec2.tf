# private ami
data "aws_ami" "dev-team-sonarqube-ami" {
  most_recent = true
  owners      = ["aws-marketplace"]

  filter {
    name   = "product-code"
    values = ["_______________ "]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

#resource "aws_ami_from_instance" "al2023" {
#  name               = "terraform-example"
#  source_instance_id = "i-xxxxxxxx"
#}

data "template_file" "sonarqube_userdata" {
  template = file("cloudinit/sonarqube_instance.yml")

  vars = {
    hostname = "sonarqube-01"
    username = data.aws_ssm_parameter.sonarqube_username.value
    password = data.aws_ssm_parameter.sonarqube_password.value
    serial   = data.aws_ssm_parameter.sonarqube_licence.value
  }
}


resource "aws_instance" "sonarqube_instance" {
  ami           = data.aws_ami.dev-team-sonarqube-ami.id
  instance_type = "t3a.xlarge"
  key_name      = "sonarqube_sp"
  user_data     = data.template_file.sonarqube_userdata.rendered
  monitoring    = "true"
  subnet_id     = aws_subnet.dev-sonarqube-subnet.id

  vpc_security_group_ids = [
    aws_security_group.sonarqube-sg.id,
  ]

  root_block_device {
    volume_type = "gp2"
    volume_size = 38
  }

  tags = {
    Name      = "Sonarqube Scanning Instance"
    ManagedBy = "terraform"
  }
}
