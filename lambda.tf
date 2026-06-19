# Primary Lambda Function
data "archive_file" "lambda_function" {
  type        = "zip"
  source_file = "${path.module}/processor/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

resource "aws_lambda_function" "narrative_generator" {
  filename         = data.archive_file.lambda_function.output_path
  function_name    = "${var.lambda_name}-${var.environment}"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = 512
  source_code_hash = data.archive_file.lambda_function.output_base64sha256

  environment {
    variables = {
      TABLE_NAME        = var.dynamodb_table
      BUCKET_NAME       = var.bucket_name
      STREAM_NAME       = var.stream_name
      USE_MOCK_AI       = tostring(var.use_mock_ai)
      AWS_ENDPOINT_URL  = var.aws_endpoint_url
      ENVIRONMENT       = var.environment
    }
  }

  tags = merge(var.tags, {
    Name = "${var.lambda_name}-${var.environment}"
  })
}

# Bedrock Lambda Function
data "archive_file" "bedrock_lambda_function" {
  type        = "zip"
  source_file = "${path.module}/processor/lambda_bedrock_narrative.py"
  output_path = "${path.module}/bedrock_lambda_function.zip"
}

resource "aws_lambda_function" "bedrock_narrative_generator" {
  filename         = data.archive_file.bedrock_lambda_function.output_path
  function_name    = "${var.bedrock_lambda_name}-${var.environment}"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.11"
  timeout         = var.bedrock_lambda_timeout
  memory_size     = var.bedrock_lambda_memory
  source_code_hash = data.archive_file.bedrock_lambda_function.output_base64sha256

  environment {
    variables = {
      TABLE_NAME        = var.dynamodb_table
      BUCKET_NAME       = var.bucket_name
      BEDROCK_MODEL_ID  = var.bedrock_model_id
      STORY_TONE        = var.story_tone
      AWS_ENDPOINT_URL  = var.aws_endpoint_url
      ENVIRONMENT       = var.environment
    }
  }

  tags = merge(var.tags, {
    Name = "${var.bedrock_lambda_name}-${var.environment}"
  })
}
