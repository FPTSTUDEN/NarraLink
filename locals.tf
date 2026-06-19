# Local variables for reuse across resources
locals {
  common_tags = {
    Project     = "NarrativeEngine"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
  
  # Resource naming conventions
  s3_bucket_name = "${var.bucket_name}-${var.environment}"
  stream_name    = "${var.stream_name}-${var.environment}"
  table_name     = "${var.dynamodb_table}-${var.environment}"
  prefs_table    = "${var.dynamodb_prefs}-${var.environment}"
}
