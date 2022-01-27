variable "region_string" {
  description = "Region"
  type = string
}

variable "handler_function" {
  description = "Full description of handler function (e.g. 'module_name.function_file.lambda_handler' => estuary_prober.app.lambda_handler)"
  type = string
}

variable "prober_function_name" {
    description = "Prober Function Name"
    type = string
}

variable "prober_arn" {
    description = "Prober ARN"
    type = string
}


variable "event" {
  description = "Cloud event to fire once per minute."
  type = map
}

variable "cloud_event_name" {
  description = "Cloud event name to create."
  type = string
}
