terraform {
  backend "gcs" {
    prefix = "envs/dev/ow-terraform-state"
    # TODO: Update this to your project's GCS bucket for Terraform state
    bucket = "your-project-tfstate"
  }
}
