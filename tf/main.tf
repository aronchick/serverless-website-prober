terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.56.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2.0"
    }
  }

  required_version = "~> 1.0"
}

provider "aws" {
  region = var.aws_region
}

module "secret_manager" {
  source  = "./modules/secret_manager"
}

module "lambda_estuary_prober" {
  source  = "./modules/lambda_estuary_prober"

  DATABASE_HOST=module.secret_manager.estuary_prober_secrets_dict.DATABASE_HOST
  DATABASE_USER=module.secret_manager.estuary_prober_secrets_dict.DATABASE_USER
  DATABASE_PASSWORD=module.secret_manager.estuary_prober_secrets_dict.DATABASE_PASSWORD
  DATABASE_NAME=module.secret_manager.estuary_prober_secrets_dict.DATABASE_NAME
  ESTUARY_TOKEN=module.secret_manager.estuary_prober_secrets_dict.ESTUARY_TOKEN
}

module "cloudwatch_scheduled_trigger" {
  source  = "./modules/cloudwatch_scheduled_trigger"

  estuary_url = "shuttle-4.estuary.tech" 
  unique_runner_id = "lambda@cloudwatchdebugging"

  estuary_prober_arn = module.lambda_estuary_prober.estuary_prober_arn
  estuary_prober_function_name = module.lambda_estuary_prober.estuary_prober_function_name

  depends_on = [
    module.lambda_estuary_prober
  ]
}