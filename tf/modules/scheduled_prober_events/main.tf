locals {
  region = var.region_string
}


module "cloudwatch_scheduled_trigger" {
  source  = "./modules/cloudwatch_scheduled_trigger"

  event = var.event

  region = local.region

  prober_arn = var.prober_arn
  prober_function_name = var.prober_function_name
  prober_cloud_event_name = var.cloud_event_name

}