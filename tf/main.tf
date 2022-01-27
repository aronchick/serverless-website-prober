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

locals {
  shuttles = toset( ["shuttle-4.estuary.tech", "shuttle-5.estuary.tech"] )

  # QmducxoYHKULWXeq5wtKoeMzie2QggYphNCVwuFuou9eWE == NY Open Dataset
  cids = toset(["QmducxoYHKULWXeq5wtKoeMzie2QggYphNCVwuFuou9eWE"])
}

provider "aws" {
  region = local.region_string
}

provider "aws" {
  alias = "secret_provider"
  region = "eu-west-1"
}

locals {
  region_string = terraform.workspace
  prober_function_name = "estuary_gateway_prober-${local.region_string}"
}

module "secret_manager" {
  source  = "./modules/secret_manager"
 
  providers = {
    aws = aws.secret_provider
  }

}
resource "aws_iam_role" "lambda_exec" {
  name = "estuaryprober_iam_role_${local.region_string}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Sid    = ""
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

module "lambda_prober" {
  source  = "./modules/lambda_prober"

  region=local.region_string
  handler_function="estuary_prober.app.lambda_handler"
  prober_function_name="${local.prober_function_name}"
  role_arn = aws_iam_role.lambda_exec.arn

  DATABASE_HOST=module.secret_manager.prober_secrets_dict.DATABASE_HOST
  DATABASE_USER=module.secret_manager.prober_secrets_dict.DATABASE_USER
  DATABASE_PASSWORD=module.secret_manager.prober_secrets_dict.DATABASE_PASSWORD
  DATABASE_NAME=module.secret_manager.prober_secrets_dict.DATABASE_NAME
  ESTUARY_TOKEN=module.secret_manager.prober_secrets_dict.ESTUARY_TOKEN
  HONEYCOMB_API_KEY=module.secret_manager.prober_secrets_dict.HONEYCOMB_API_KEY

}

module "scheduled_prober_events" {
  source  = "./modules/scheduled_prober_events"

  for_each = local.shuttles

  region_string = local.region_string
  handler_function = "estuary_prober.app.lambda_handler"
  prober_function_name = module.lambda_prober.prober_function_name
  prober_arn = module.lambda_prober.prober_arn

  cloud_event_name = "${local.prober_function_name}-${each.key}"

  event = tomap({
    "host" = "${each.key}",
    "region" = "${local.region_string}"
    "runner" = "lambda@${local.prober_function_name}"
    "timeout" = 60
  })

  depends_on = [
    module.secret_manager,
    resource.aws_iam_role_policy_attachment.lambda_policy
  ]
}
