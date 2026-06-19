# DynamoDB Tables
resource "aws_dynamodb_table" "narrative_state" {
  name           = var.dynamodb_table
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "pk"
  range_key      = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "gsi1sk"
    type = "S"
  }

  global_secondary_index {
    name            = "GSI1"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }

  tags = merge(var.tags, {
    Name = var.dynamodb_table
  })
}

resource "aws_dynamodb_table" "narrative_preferences" {
  name           = var.dynamodb_prefs
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = merge(var.tags, {
    Name = var.dynamodb_prefs
  })
}
