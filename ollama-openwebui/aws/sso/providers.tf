provider "aws" {
  # Only required if custom config or credentials file names.
  shared_config_files      = ["/<    >/.aws/custom_config"]
  shared_credentials_files = ["/<    >/.aws/custom_credentials"]

  # Interpolation is possible here
  profile                  = "${var.env}"
  region = "us-west-1"
}