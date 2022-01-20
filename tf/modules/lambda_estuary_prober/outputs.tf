output "estuary_prober_function_name" {
    description = "Estuary Prober Function Name"
    value = aws_lambda_function.estuary_prober.function_name
}

output "estuary_prober_arn" {
    description = "Estuary Prober ARN"
    value = aws_lambda_function.estuary_prober.arn
}


output "lambda_bucket_id" {
    description = "Bucket ID for the lambda zip"
    value = aws_s3_bucket.lambda_bucket.id
}