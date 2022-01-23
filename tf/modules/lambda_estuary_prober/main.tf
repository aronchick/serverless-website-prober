resource "random_pet" "lambda_bucket_name" {
  prefix = "${var.region}-pl-benchmarking-functions"
  length = 2
}

resource "aws_s3_bucket" "lambda_bucket" {
  bucket = random_pet.lambda_bucket_name.id

  acl           = "private"
  force_destroy = true
}

data "archive_file" "estuaryproberzip" {
  type = "zip"

  source_dir  = "${path.cwd}/build/EstuaryProber"
  output_path = "${path.cwd}/package/EstuaryProber.zip"
}


resource "aws_s3_bucket_object" "estuary_prober" {
  bucket = aws_s3_bucket.lambda_bucket.id

  key    = "estuaryprober.zip"
  source = data.archive_file.estuaryproberzip.output_path

  etag = filemd5(data.archive_file.estuaryproberzip.output_path)
}

resource "aws_lambda_function" "estuary_prober" {
  function_name = "EstuaryProber-${var.region}"

  s3_bucket = aws_s3_bucket.lambda_bucket.id
  s3_key    = aws_s3_bucket_object.estuary_prober.key

  runtime = "python3.9"
  handler = "estuary_prober.app.lambda_handler"
  timeout = 60

  source_code_hash = data.archive_file.estuaryproberzip.output_base64sha256

  role = aws_iam_role.lambda_exec.arn

  environment {
    variables = {
      DATABASE_HOST=var.DATABASE_HOST
      DATABASE_USER=var.DATABASE_USER
      DATABASE_PASSWORD=var.DATABASE_PASSWORD
      DATABASE_NAME=var.DATABASE_NAME
      ESTUARY_TOKEN=var.ESTUARY_TOKEN
      HONEYCOMB_API_KEY=var.HONEYCOMB_API_KEY
      HONEYCOMB_DATASET=var.HONEYCOMB_DATASET
    }
  }
}


resource "aws_iam_role" "lambda_exec" {
  name = "estuaryprober_iam_role_${var.region}"

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
