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
  region = local.region_string
}

provider "aws" {
  alias = "secret_provider"
  region = "eu-west-1"
}

locals {
  region_string = terraform.workspace
}

module "secret_manager" {
  source  = "./modules/secret_manager"
 
  providers = {
    aws = aws.secret_provider
  }

}
resource "aws_iam_role" "lambda_exec" {
  name = "prober-iam-role-${local.region_string}"

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
  role_arn = aws_iam_role.lambda_exec.arn

  DATABASE_HOST=module.secret_manager.prober_secrets_dict.DATABASE_HOST
  DATABASE_USER=module.secret_manager.prober_secrets_dict.DATABASE_USER
  DATABASE_PASSWORD=module.secret_manager.prober_secrets_dict.DATABASE_PASSWORD
  DATABASE_NAME=module.secret_manager.prober_secrets_dict.DATABASE_NAME
  ESTUARY_TOKEN=module.secret_manager.prober_secrets_dict.ESTUARY_TOKEN
  HONEYCOMB_API_KEY=module.secret_manager.prober_secrets_dict.HONEYCOMB_API_KEY

}



locals {
    shuttles_to_test_in_file = csvdecode(file("${path.module}/modules/events/estuary_prober_shuttles_to_test.csv"))
    estuary_prober_events = [for s in local.shuttles_to_test_in_file : {"host" = "${s.shuttle}", "timeout"= 10, "prober"= "estuary_prober", "event_suffix"= "${s.event_suffix}"}]
}

locals {
    cids_to_test_in_file = csvdecode(file("${path.module}/modules/events/cid_prober_cids_to_test.csv"))
    cid_prober_events = [for c in local.cids_to_test_in_file : {"cid" = "${c.cid}", "timeout": 10, "prober"= "cid_prober", "event_suffix"= "${c.data_to_test}"}]
}

locals {
    // Flatten probably unnecessary
    event_output = flatten(concat(local.estuary_prober_events, local.cid_prober_events))
}
module "scheduled_prober_events" {
  source  = "./modules/scheduled_prober_events"

  for_each = {for event in local.event_output:  "${event.prober}_${local.region_string}_${event.event_suffix}" => event}

  region_string = local.region_string
  handler_function = "muxer.app.lambda_handler"
  prober_arn = module.lambda_prober.prober_arn
  prober_function_name = "${each.key}"

  cloud_event_name = "${each.key}"

  event = merge(each.value, {
    "region" = "${local.region_string}"
    "runner" = "lambda@${each.key}"
    "timeout" = 60
  })

  depends_on = [
    module.secret_manager,
    resource.aws_iam_role_policy_attachment.lambda_policy
  ]
}
