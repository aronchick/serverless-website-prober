terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.56.0"
    }
  }

  required_version = "~> 1.0"
}

data "aws_secretsmanager_secret_version" "estuary_prober_secrets_tf" {
    secret_id = "EstuaryProberSecrets"
}