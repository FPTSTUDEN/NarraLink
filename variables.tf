variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_endpoint_url" {
  description = "AWS endpoint URL (for LocalStack)"
  type        = string
  default     = "http://localhost:4566"
}

variable "aws_access_key_id" {
  description = "AWS access key ID"
  type        = string
  default     = "test"
}

variable "aws_secret_access_key" {
  description = "AWS secret access key"
  type        = string
  default     = "test"
}

variable "bucket_name" {
  description = "S3 bucket name"
  type        = string
  default     = "narrative-store"
}

variable "stream_name" {
  description = "Kinesis stream name"
  type        = string
  default     = "user-events"
}

variable "dynamodb_table" {
  description = "DynamoDB table name"
  type        = string
  default     = "narrative-state"
}

variable "dynamodb_prefs" {
  description = "DynamoDB preferences table name"
  type        = string
  default     = "narrative-preferences"
}

variable "lambda_name" {
  description = "Primary Lambda function name"
  type        = string
  default     = "narrative-generator"
}

variable "bedrock_lambda_name" {
  description = "Bedrock Lambda function name"
  type        = string
  default     = "narrative-bedrock-generator"
}

variable "bedrock_model_id" {
  description = "Bedrock model ID"
  type        = string
  default     = "anthropic.claude-3-sonnet-20240229-v1:0"
}

variable "story_tone" {
  description = "Default story tone"
  type        = string
  default     = "reflective"
}

variable "use_mock_ai" {
  description = "Use mock AI for testing"
  type        = bool
  default     = true
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}

variable "bedrock_lambda_timeout" {
  description = "Bedrock Lambda timeout in seconds"
  type        = number
  default     = 600
}

variable "bedrock_lambda_memory" {
  description = "Bedrock Lambda memory in MB"
  type        = number
  default     = 1769
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {
    Project     = "NarrativeEngine"
    ManagedBy   = "Terraform"
  }
}
