resource "random_pet" "lambda_bucket_name" {
  prefix = "${var.region}-probers"
  length = 1
}

resource "aws_s3_bucket" "lambda_bucket" {
  bucket = random_pet.lambda_bucket_name.id

  acl           = "private"
  force_destroy = true
}

data "archive_file" "lambdaproberzip" {
  type = "zip"

  source_dir  = "${path.cwd}/build/lambdaprober"
  output_path = "${path.cwd}/package/lambdaprober.zip"
}


resource "aws_s3_bucket_object" "prober_bucket_object" {
  bucket = aws_s3_bucket.lambda_bucket.id

  key    = "lambdaprober.zip"
  source = data.archive_file.lambdaproberzip.output_path

  etag = filemd5(data.archive_file.lambdaproberzip.output_path)
}

resource "aws_lambda_function" "prober" {
  function_name = "${var.prober_function_name}"

  s3_bucket = aws_s3_bucket.lambda_bucket.id
  s3_key    = aws_s3_bucket_object.prober_bucket_object.key

  runtime = "python3.9"
  handler = var.handler_function
  timeout = 60

  source_code_hash = data.archive_file.lambdaproberzip.output_base64sha256

  role = var.role_arn

  environment {
    variables = {
      DATABASE_HOST=var.DATABASE_HOST
      DATABASE_USER=var.DATABASE_USER
      DATABASE_PASSWORD=var.DATABASE_PASSWORD
      DATABASE_NAME=var.DATABASE_NAME
      ESTUARY_TOKEN=var.ESTUARY_TOKEN
      HONEYCOMB_API_KEY=var.HONEYCOMB_API_KEY
    }
  }
}

