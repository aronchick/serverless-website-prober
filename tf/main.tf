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


resource "random_pet" "lambda_bucket_name" {
  prefix = "pl-benchmarking-functions"
  length = 4
}

resource "aws_s3_bucket" "lambda_bucket" {
  bucket = random_pet.lambda_bucket_name.id

  acl           = "private"
  force_destroy = true
}

data "archive_file" "estuaryproberzip" {
  type = "zip"

  source_dir  = "${path.module}/build/EstuaryProber"
  output_path = "${path.module}/package/estuaryprober.zip"
}


resource "aws_s3_bucket_object" "estuary_prober" {
  bucket = aws_s3_bucket.lambda_bucket.id

  key    = "estuaryprober.zip"
  source = data.archive_file.estuaryproberzip.output_path

  etag = filemd5(data.archive_file.estuaryproberzip.output_path)
}

resource "aws_lambda_function" "estuary_prober" {
  function_name = "EstuaryProber"

  s3_bucket = aws_s3_bucket.lambda_bucket.id
  s3_key    = aws_s3_bucket_object.estuary_prober.key

  runtime = "python3.9"
  handler = "estuary_prober.app.lambda_handler"
  timeout = 10

  source_code_hash = data.archive_file.estuaryproberzip.output_base64sha256

  role = aws_iam_role.lambda_exec.arn

  environment {
    variables = {
      DATABASE_HOST=module.secret_manager.estuary_prober_secrets_dict.DATABASE_HOST
      DATABASE_USER=module.secret_manager.estuary_prober_secrets_dict.DATABASE_USER
      DATABASE_PASSWORD=module.secret_manager.estuary_prober_secrets_dict.DATABASE_PASSWORD
      DATABASE_NAME=module.secret_manager.estuary_prober_secrets_dict.DATABASE_NAME
      ESTUARY_TOKEN=module.secret_manager.estuary_prober_secrets_dict.ESTUARY_TOKEN
    }
  }
}

resource "aws_cloudwatch_log_group" "estuary_prober" {
  name = "/aws/lambda/${aws_lambda_function.estuary_prober.function_name}"

  retention_in_days = 30
}

resource "aws_iam_role" "lambda_exec" {
  name = "estuaryprober_iam_role"

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

resource "aws_cloudwatch_event_rule" "every_one_minutes" {
    name = "every-one-minutes"
    description = "Fires every one minutes"
    schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "fire_prober_every_one_minutes" {
    rule = "${aws_cloudwatch_event_rule.every_one_minutes.name}"
    target_id = "check"
    arn = "${aws_lambda_function.estuary_prober.arn}"
  input = <<JSON
{
  "host": "shuttle-4.estuary.tech",
  "runner": "lambda@cloudwatchdebugging"
}
JSON
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_estuary_prober" {
    statement_id = "AllowExecutionFromCloudWatch"
    action = "lambda:InvokeFunction"
    function_name = "${aws_lambda_function.estuary_prober.function_name}"
    principal = "events.amazonaws.com"
    source_arn = "${aws_cloudwatch_event_rule.every_one_minutes.arn}"
}