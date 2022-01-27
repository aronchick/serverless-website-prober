resource "aws_cloudwatch_event_rule" "every_one_minutes" {
    name = "1m-${var.prober_cloud_event_name}"
    description = "Fires every one minutes"
    schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "fire_prober_every_one_minutes" {
    rule = "${aws_cloudwatch_event_rule.every_one_minutes.name}"
    target_id = "check"
    arn = "${var.prober_arn}"
    input = jsonencode(var.event)
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_prober" {
    action = "lambda:InvokeFunction"
    function_name = "${var.prober_arn}"
    principal = "events.amazonaws.com"
    source_arn = "${aws_cloudwatch_event_rule.every_one_minutes.arn}"
}