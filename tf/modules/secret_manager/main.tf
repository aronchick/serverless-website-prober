
data "aws_secretsmanager_secret_version" "estuary_prober_secrets_tf" {
    secret_id = "EstuaryProberSecrets"
}