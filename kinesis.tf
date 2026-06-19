# Kinesis Stream
resource "aws_kinesis_stream" "user_events" {
  name             = var.stream_name
  # stream_mode      = "ON_DEMAND"
  shard_count      = 1
  retention_period = 24

  tags = merge(var.tags, {
    Name = var.stream_name
  })
}
