# Configure the Azure Provider
provider "azurerm" {
  version                    = "= 3.85.0"
  skip_provider_registration = true
  features {}
}

provider "random" {
  version = "~> 3.6"
}

provider "template" {
  version = "~> 2.2"
}
