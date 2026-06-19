output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.narrative_store.id
}

output "kinesis_stream_name" {
  description = "Kinesis stream name"
  value       = aws_kinesis_stream.user_events.name
}

output "kinesis_stream_arn" {
  description = "Kinesis stream ARN"
  value       = aws_kinesis_stream.user_events.arn
}

output "dynamodb_tables" {
  description = "DynamoDB table names"
  value = {
    narrative_state      = aws_dynamodb_table.narrative_state.name
    narrative_preferences = aws_dynamodb_table.narrative_preferences.name
  }
}

output "lambda_function_names" {
  description = "Lambda function names"
  value = {
    narrative_generator       = aws_lambda_function.narrative_generator.function_name
    bedrock_narrative_generator = aws_lambda_function.bedrock_narrative_generator.function_name
  }
}

output "lambda_function_arns" {
  description = "Lambda function ARNs"
  value = {
    narrative_generator       = aws_lambda_function.narrative_generator.arn
    bedrock_narrative_generator = aws_lambda_function.bedrock_narrative_generator.arn
  }
}

output "event_source_mapping" {
  description = "Event source mapping UUID"
  value       = aws_lambda_event_source_mapping.kinesis_trigger.uuid
}

output "iam_role_arn" {
  description = "IAM role ARN"
  value       = aws_iam_role.lambda_role.arn
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}
