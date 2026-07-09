resource "aws_cloudwatch_log_group" "sonarqube" {
  name = "/sonarqube-scans"

  tags = {
    Environment = "production"
    Application = "sonarqube scans"
  }
}

resource "aws_cloudwatch_log_subscription_filter" "log_subscription" {
  name = "log_subscription"

  log_group_name  = "/sonarqube-scans"
  filter_pattern  = ""
  destination_arn = "arn:aws:logs:us-west-2:885513274347:destination:__________________"
}
