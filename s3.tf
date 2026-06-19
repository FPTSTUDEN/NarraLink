# S3 Bucket
resource "aws_s3_bucket" "narrative_store" {
  bucket = var.bucket_name
  force_destroy = true

  tags = merge(var.tags, {
    Name = var.bucket_name
  })
}

resource "aws_s3_bucket_versioning" "narrative_store" {
  bucket = aws_s3_bucket.narrative_store.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "narrative_store" {
  bucket = aws_s3_bucket.narrative_store.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "narrative_store" {
  bucket = aws_s3_bucket.narrative_store.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
