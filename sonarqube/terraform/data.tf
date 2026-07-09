data "aws_ssm_parameter" "sonarqube_username" {
  name = "/sonarqube/username"
}

data "aws_ssm_parameter" "sonarqube_password" {
  name = "/sonarqube/password"
}

data "aws_ssm_parameter" "sonarqube_licence" {
  name = "/sonarqube/licence"
}

data "aws_ssm_parameter" "account_id" {
  name = "/sonarqube/account_id"
}
