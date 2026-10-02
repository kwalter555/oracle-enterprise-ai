terraform {
  required_version = ">= 1.5.0, < 1.6.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "9.7.1"
    }
  }
}

# Resource Manager supplies authentication. No API key files or credentials here.
provider "oci" {
  region = var.region
}

# IAM resources must be managed through the tenancy's home region.
provider "oci" {
  alias  = "home"
  region = var.home_region
}
