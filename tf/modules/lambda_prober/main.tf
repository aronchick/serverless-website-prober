resource "random_pet" "lambda_bucket_name" {
  prefix = "${var.region}-probers"
  length = 1
}

resource "aws_s3_bucket" "lambda_bucket" {
  bucket = random_pet.lambda_bucket_name.id

  acl           = "private"
  force_destroy = true
}

data "archive_file" "proberzip" {
  type = "zip"

  source_dir  = "${path.cwd}/build/prober"
  output_path = "${path.cwd}/package/prober.zip"
}


resource "aws_s3_bucket_object" "prober_bucket_object" {
  bucket = aws_s3_bucket.lambda_bucket.id

  key    = "prober.zip"
  source = data.archive_file.proberzip.output_path

  etag = filemd5(data.archive_file.proberzip.output_path)
}

resource "aws_lambda_function" "prober" {
  function_name = "muxer_app_lambda_handler"

  s3_bucket = aws_s3_bucket.lambda_bucket.id
  s3_key    = aws_s3_bucket_object.prober_bucket_object.key

  runtime = "python3.9"
  handler = "muxer.app.lambda_handler"
  timeout = 60

  source_code_hash = data.archive_file.proberzip.output_base64sha256

  role = var.role_arn

  environment {
    variables = {
      DATABASE_HOST=var.DATABASE_HOST
      DATABASE_USER=var.DATABASE_USER
      DATABASE_PASSWORD=var.DATABASE_PASSWORD
      DATABASE_NAME=var.DATABASE_NAME
      ESTUARY_TOKEN=var.ESTUARY_TOKEN
      HONEYCOMB_API_KEY=var.HONEYCOMB_API_KEY
      SOURCE_CODE_HASH=data.archive_file.proberzip.output_base64sha256
    }
  }
}

