variable "DATABASE_HOST" {
  description = "Name of the database host."
  type        = string
}

variable "DATABASE_USER" {
  description = "Name of the database user."
  type        = string
}

variable "DATABASE_PASSWORD" {
  description = "Database password."
  type        = string
}

variable "DATABASE_NAME" {
  description = "Name of the database."
  type        = string
}

variable "ESTUARY_TOKEN" {
  description = "Estuary token."
  type        = string
}

variable "region" {
  description = "Region of caller."
  type = string
}

variable "HONEYCOMB_API_KEY"{
  description = "HONEYCOMB_API_KEY"
  type=string
}

variable "lambda_bucket_id" {
  description = "Bucket ID for lambda zip."
  type = string
}

variable "lambda_bucket_key" {
  description = "Bucket Key for lambda zip."
  type = string
}

variable "lambdazip_output_base64sha256" {
  description = "SHA Key for lambda zip."
  type = string
}