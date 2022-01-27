resource "aws_lambda_function" "cid_prober" {
  function_name = "CIDProber-${var.region}"

  s3_bucket = var.lambda_bucket_id
  s3_key    = var.lambda_bucket_key

  runtime = "python3.9"
  handler = "cid_prober.app.lambda_handler"
  timeout = 60

  source_code_hash = var.lambdazip_output_base64sha256

  role = aws_iam_role.lambda_exec.arn

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
