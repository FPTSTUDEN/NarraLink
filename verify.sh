#!/bin/bash
source aws_cmd.sh
load_env

# Test S3
aws_cmd s3 ls

# Test Kinesis
aws_cmd kinesis list-streams

# Test DynamoDB
aws_cmd dynamodb list-tables

# Test Lambda
aws_cmd lambda list-functions

# Inspect emulator state
curl http://localhost:4566/_floci/status