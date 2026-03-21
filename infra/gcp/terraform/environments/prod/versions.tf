terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.9"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.9"
    }
  }
}
