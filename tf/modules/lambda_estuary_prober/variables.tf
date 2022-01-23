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

variable "HONEYCOMB_DATASET"{
  description = "HONEYCOMB_DATASET"
  type=string
}
