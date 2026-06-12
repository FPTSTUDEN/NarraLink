#!/bin/bash
# Load environment variables
load_env() {
    # Colors for output
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m' # No Color
    if [ -f ../.env ]; then
        export $(cat ../.env | grep -v '^#' | xargs)
    else
        echo -e "${YELLOW}⚠️  .env file not found, using defaults${NC}"
        export AWS_ENDPOINT_URL=http://localhost:4566
        export AWS_REGION=us-east-1
        export AWS_ACCESS_KEY_ID=test
        export AWS_SECRET_ACCESS_KEY=test
    fi
}

aws_cmd() {
    aws --endpoint-url=$AWS_ENDPOINT_URL \
        --region $AWS_REGION \
        "$@"
}