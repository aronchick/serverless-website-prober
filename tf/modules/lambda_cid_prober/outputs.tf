output "cid_prober_function_name" {
    description = "Estuary Prober Function Name"
    value = aws_lambda_function.estuary_prober.function_name
}

output "cid_prober_arn" {
    description = "Estuary Prober ARN"
    value = aws_lambda_function.estuary_prober.arn
}