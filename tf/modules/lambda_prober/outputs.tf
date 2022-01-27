output "prober_function_name" {
    description = "Prober Function Name"
    value = aws_lambda_function.prober.function_name
}

output "prober_arn" {
    description = "Prober ARN"
    value = aws_lambda_function.prober.arn
}


output "lambda_bucket_id" {
    description = "Bucket ID for the lambda zip"
    value = aws_s3_bucket.lambda_bucket.id
}

output "lambda_bucket_key" {
    description = "Bucket key for the lambda zip"
    value = aws_s3_bucket_object.prober_bucket_object
}

output "lambdazip_output_base64sha256" {
    description = "Sha256 for the lambda zip"
    value = data.archive_file.lambdaproberzip.output_base64sha256
}
