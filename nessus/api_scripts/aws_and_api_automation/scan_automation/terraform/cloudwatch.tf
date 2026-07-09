resource "aws_cloudwatch_log_group" "nessus_data" {
  name = "/nessus-scans"

  tags = {
    Environment = "production"
    Application = "Nessus scans"
  }
}

resource "aws_cloudwatch_log_subscription_filter" "log_subscription" {
  name = "log_subscription"

  log_group_name  = "/nessus-scans"
  filter_pattern  = ""
  destination_arn = "arn:aws:logs:us-west-2:885513274347:destination:__________________"
}
