output "estuary_prober_secrets_dict" {
    description = "Estuary Prober Secrets Dict"
    value = jsondecode(
    data.aws_secretsmanager_secret_version.estuary_prober_secrets_tf.secret_string
    ) 
}