#!/bin/bash
#./setup.sh
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Narrative Engine Infrastructure Setup${NC}\n"

# Load environment variables
if [ -f ../.env ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
else
    echo -e "${YELLOW}⚠️  .env file not found, using defaults${NC}"
    export AWS_ENDPOINT_URL=http://localhost:4566
    export AWS_REGION=us-east-1
    export AWS_ACCESS_KEY_ID=test
    export AWS_SECRET_ACCESS_KEY=test
fi

# Wait for emulator to be ready
echo -e "${YELLOW}⏳ Waiting for AWS emulator to be ready...${NC}"
max_retries=30
counter=0
until curl -s -f http://localhost:4566/_floci/health > /dev/null 2>&1; do
    counter=$((counter + 1))
    if [ $counter -gt $max_retries ]; then
        echo -e "${RED}❌ Emulator failed to start${NC}"
        exit 1
    fi
    sleep 1
done
echo -e "${GREEN}✅ Emulator is ready${NC}\n"

# Function to run AWS CLI commands
aws_cmd() {
    aws --endpoint-url=$AWS_ENDPOINT_URL \
        --region $AWS_REGION \
        "$@"
}

echo -e "${GREEN}📦 Creating resources...${NC}\n"

# 1. Create S3 bucket for raw events
echo "📁 Creating S3 bucket: narrative-store"
aws_cmd s3 mb s3://narrative-store 2>/dev/null || echo "  Bucket already exists"
aws_cmd s3api put-bucket-versioning \
    --bucket narrative-store \
    --versioning-configuration Status=Enabled 2>/dev/null || true
aws_cmd s3api put-bucket-encryption \
    --bucket narrative-store \
    --server-side-encryption-configuration '{
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    }' 2>/dev/null || true

# 2. Create Kinesis stream
echo "📊 Creating Kinesis stream: user-events"
aws_cmd kinesis create-stream \
    --stream-name user-events \
    --shard-count 1 \
    --stream-mode-details '{
        "StreamMode": "ON_DEMAND"
    }' 2>/dev/null || echo "  Stream already exists"

# Wait for stream to become active
echo "  Waiting for stream to activate..."
while true; do
    status=$(aws_cmd kinesis describe-stream --stream-name user-events \
        --query 'StreamDescription.StreamStatus' --output text 2>/dev/null)
    if [ "$status" = "ACTIVE" ]; then
        break
    fi
    sleep 2
done
echo "  Stream active"

# 3. Create DynamoDB tables
echo "🗄️  Creating DynamoDB tables"

# Main state table
aws_cmd dynamodb create-table \
    --table-name narrative-state \
    --attribute-definitions \
        AttributeName=pk,AttributeType=S \
        AttributeName=sk,AttributeType=S \
        AttributeName=gsi1pk,AttributeType=S \
        AttributeName=gsi1sk,AttributeType=S \
    --key-schema \
        AttributeName=pk,KeyType=HASH \
        AttributeName=sk,KeyType=RANGE \
    --global-secondary-indexes \
        '[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"}
                ],
                "Projection": {"ProjectionType": "ALL"}
            }
        ]' \
    --billing-mode PAY_PER_REQUEST 2>/dev/null || echo "  Table 'narrative-state' already exists"

# User preferences table
aws_cmd dynamodb create-table \
    --table-name narrative-preferences \
    --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
    --key-schema \
        AttributeName=user_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST 2>/dev/null || echo "  Table 'narrative-preferences' already exists"

# 4. Create Lambda function (will be updated with code later)
echo "⚡ Creating Lambda function: narrative-generator"
cat > /tmp/lambda-init.py << 'EOF'
def lambda_handler(event, context):
    print("Lambda initialized. Waiting for deployment...")
    return {"statusCode": 200, "body": "Ready"}
EOF

zip -j /tmp/lambda-init.zip /tmp/lambda-init.py 2>/dev/null

aws_cmd lambda create-function \
    --function-name narrative-generator \
    --runtime python3.11 \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --handler lambda-init.lambda_handler \
    --zip-file fileb:///tmp/lambda-init.zip \
    --environment Variables="{ \
        TABLE_NAME=narrative-state, \
        BUCKET_NAME=narrative-store, \
        STREAM_NAME=user-events \
    }" 2>/dev/null || echo "  Function already exists"

# 5. Create EventBridge schedule for daily processing
echo "⏰ Creating EventBridge schedule: daily-narrative"
aws_cmd scheduler create-schedule \
    --name daily-narrative \
    --schedule-expression "cron(30 22 * * ? *)" \
    --flexible-time-window '{ "Mode": "OFF" }' \
    --target '{
        "Arn": "arn:aws:lambda:us-east-1:000000000000:function:narrative-generator",
        "RoleArn": "arn:aws:iam::000000000000:role/scheduler-role",
        "Input": "{\"action\": \"generate_daily_narrative\"}"
    }' 2>/dev/null || echo "  Schedule already exists"

# 6. Create IAM roles and policies (mock for emulator)
echo "🔐 Setting up IAM roles (mock)"
aws_cmd iam create-role \
    --role-name lambda-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' 2>/dev/null || echo "  Role already exists"

# 7. Set up Kinesis trigger for Lambda
echo "🔌 Setting up Kinesis trigger"
aws_cmd lambda create-event-source-mapping \
    --function-name narrative-generator \
    --event-source-arn "arn:aws:kinesis:us-east-1:000000000000:stream/user-events" \
    --starting-position LATEST 2>/dev/null || echo "  Trigger already exists"

echo -e "\n${GREEN}✅ Infrastructure setup complete!${NC}\n"

# Display summary
echo -e "${GREEN}📋 Resource Summary:${NC}"
echo "  • S3 Bucket:          s3://narrative-store"
echo "  • Kinesis Stream:     user-events"
echo "  • DynamoDB Tables:    narrative-state, narrative-preferences"
echo "  • Lambda Function:    narrative-generator"
echo "  • Schedule:           daily-narrative (10:30 PM daily)"

echo -e "\n${YELLOW}💡 Next Steps:${NC}"
echo "  1. Run: docker-compose up -d"
echo "  2. Test setup: ./scripts/health_check.sh"
echo "  3. Deploy Lambda code: ./infrastructure/deploy_lambda.sh"