
resource "aws_cloudwatch_log_group" "estuary_prober" {
  name = "/aws/lambda/${var.estuary_prober_function_name}-${var.region}-${var.estuary_url}"

  retention_in_days = 30
}

resource "aws_cloudwatch_event_rule" "every_one_minutes" {
    name = "every-one-minutes-${var.region}-${var.estuary_url}"
    description = "Fires every one minutes"
    schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "fire_prober_every_one_minutes" {
    rule = "${aws_cloudwatch_event_rule.every_one_minutes.name}"
    target_id = "check"
    arn = "${var.estuary_prober_arn}"
  input = <<JSON
{
  "host": "${var.estuary_url}",
  "runner": "lambda@${var.unique_runner_id}",
  "region": "${var.region}"
}
JSON
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_estuary_prober" {
    action = "lambda:InvokeFunction"
    function_name = "${var.estuary_prober_function_name}"
    principal = "events.amazonaws.com"
    source_arn = "${aws_cloudwatch_event_rule.every_one_minutes.arn}"
}