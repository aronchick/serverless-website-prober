variable "estuary_url" {
  description = "Url of the estuary host to probe."
  type        = string
}

variable "unique_runner_id" {
  description = "Unique id of the runner."
  type        = string
}

variable "estuary_prober_arn" {
  description = "Estuary Prober ARN."
  type        = string
}

variable "estuary_prober_function_name" {
  description = "Estuary Prober Function Name."
  type        = string
}

variable "region" {
  description = "Name of the region being deployed to."
  type    = string
}
