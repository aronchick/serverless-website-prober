terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.56.0"
    }
  }

  required_version = "~> 1.0"
}

data "aws_secretsmanager_secret_version" "prober_secrets_tf" {
    // Legacy name - also, this is in eu-west-1. Probably should duplicate.
    secret_id = "EstuaryProberSecrets"
}