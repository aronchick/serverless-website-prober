variable "prober_cloud_event_name" {
  description = "Prober cloud event name"
  type =  string
}

variable "event" {
  description = "map of all k/v to pass to the prober"
  type        = map(string)
}

variable "prober_arn" {
  description = "Prober ARN."
  type        = string
}

variable "prober_function_name" {
  description = "Prober Function Name."
  type        = string
}

variable "region" {
  description = "Name of the region being deployed to."
  type    = string
}

