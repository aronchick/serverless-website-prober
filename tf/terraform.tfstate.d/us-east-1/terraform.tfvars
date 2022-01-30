terraform {
  backend "s3" {
    bucket               = "terraform-state-bucket"
    dynamodb_table       = "terraform-state-lock-table"
    encrypt              = true
    key                  = "terraform.tfstate"
    region               = "us-east-1"
    workspace_key_prefix = "prober"
  }
}