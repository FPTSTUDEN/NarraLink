#!/bin/bash
source awslocal.sh
load_env

ENDPOINT=${AWS_ENDPOINT_URL:-http://localhost:4566}

echo "🏥 Running health checks...\n"

# Check emulator
echo -n "Emulator status: "
if curl -s -f $ENDPOINT/_floci/health > /dev/null; then
    echo "✅ Healthy"
else
    echo "❌ Unhealthy"
    exit 1
fi

echo -n "Infra status: "
# Test S3
awslocal s3 ls

# Test Kinesis
awslocal kinesis list-streams

# Test DynamoDB
awslocal dynamodb list-tables

# Test Lambda
awslocal lambda list-functions

# Check S3
echo -n "S3 bucket: "
if awslocal s3 ls s3://narrative-store > /dev/null 2>&1; then
    echo "✅ Accessible"
else
    echo "❌ Not accessible"
fi

# Check Kinesis
echo -n "Kinesis stream: "
if awslocal kinesis describe-stream --stream-name user-events > /dev/null 2>&1; then
    echo "✅ Active"
else
    echo "❌ Not found"
fi

# Check DynamoDB
echo -n "DynamoDB tables: "
tables=$(awslocal dynamodb list-tables --query 'TableNames[*]' --output text)
if echo "$tables" | grep -q "narrative-state"; then
    echo "✅ Tables exist"
else
    echo "❌ Missing tables"
fi

echo "\n✨ All systems operational"