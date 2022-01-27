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

variable "HONEYCOMB_API_KEY"{
  description = "HONEYCOMB_API_KEY"
  type=string
}

variable "handler_function" {
  description = "Full description of handler function (e.g. 'module_name.function_file.lambda_handler' => estuary_prober.app.lambda_handler)"
  type = string
}

variable "prober_function_name" {
  description = "Name of the prober."
  type = string
}

variable "role_arn" {
  description = "The ARN of the policy that is used to set the permissions boundary for the IAM role for the Lambda function."
  type        = string
}

variable "region" {
  description = "Region of caller."
  type = string
}
