# EventBridge Rule for Daily Schedule (Optional)
resource "aws_cloudwatch_event_rule" "daily_narrative" {
  count               = var.environment == "prod" ? 1 : 0
  name                = "daily-narrative-generation-${var.environment}"
  description         = "Trigger daily narrative generation at 2 AM"
  schedule_expression = "cron(0 2 * * ? *)"
  state               = "ENABLED"

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "daily_narrative_target" {
  count     = var.environment == "prod" ? 1 : 0
  rule      = aws_cloudwatch_event_rule.daily_narrative[0].name
  target_id = "1"
  arn       = aws_lambda_function.bedrock_narrative_generator.arn
  input = jsonencode({
    action  = "generate_daily"
    user_id = "all-users"
  })
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow_eventbridge" {
  count         = var.environment == "prod" ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridge-${var.environment}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bedrock_narrative_generator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_narrative[0].arn
}
