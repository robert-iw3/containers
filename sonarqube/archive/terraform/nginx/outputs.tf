# Define an output value of the IP of the EC2 instance
output "aws-nginx-ip" {
  description = "Public IP address of EC2 instances"
  value = aws_instance.web_sonarqube_01.public_ip
}