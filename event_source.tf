# Event Source Mapping (Kinesis → Lambda)
resource "aws_lambda_event_source_mapping" "kinesis_trigger" {
  event_source_arn  = aws_kinesis_stream.user_events.arn
  function_name    = aws_lambda_function.narrative_generator.arn
  starting_position = "LATEST"
  batch_size       = 100
  enabled          = true
}
