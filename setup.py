#!/usr/bin/env python3
"""
Infrastructure setup for Narrative Engine using boto3
"""

import os
import time
import zipfile
import tempfile
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

# Colors for output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'

# Changes directory to project root
# os.chdir(Path(__file__).parent.parent)

def load_env():
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    os.environ[key] = val
    else:
        print(f"{YELLOW}⚠️  .env file not found, using defaults{NC}")
        os.environ.setdefault('AWS_ENDPOINT_URL', 'http://localhost:4566')
        os.environ.setdefault('AWS_REGION', 'us-east-1')
        os.environ.setdefault('AWS_ACCESS_KEY_ID', 'test')
        os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'test')

def get_client(service):
    """Get boto3 client with custom endpoint"""
    return boto3.client(
        service,
        endpoint_url=os.environ['AWS_ENDPOINT_URL'],
        region_name=os.environ['AWS_REGION'],
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY']
    )

def wait_for_emulator():
    """Wait for LocalStack to be ready"""
    import requests
    print(f"{YELLOW}⏳ Waiting for AWS emulator to be ready...{NC}")
    for _ in range(30):
        try:
            requests.get('http://localhost:4566/_localstack/health', timeout=1)
            print(f"{GREEN}✅ Emulator is ready{NC}\n")
            return
        except:
            time.sleep(1)
    print(f"{RED}❌ Emulator failed to start{NC}")
    exit(1)

def create_s3_bucket(s3):
    """Create S3 bucket for raw events"""
    print("📁 Creating S3 bucket: narrative-store")
    try:
        s3.create_bucket(Bucket='narrative-store')
        s3.put_bucket_versioning(
            Bucket='narrative-store',
            VersioningConfiguration={'Status': 'Enabled'}
        )
        s3.put_bucket_encryption(
            Bucket='narrative-store',
            ServerSideEncryptionConfiguration={
                'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]
            }
        )
    except ClientError as e:
        if 'BucketAlreadyExists' not in str(e):
            print(f"  {e}")

def create_kinesis_stream(kinesis):
    """Create Kinesis stream"""
    print("📊 Creating Kinesis stream: user-events")
    try:
        kinesis.create_stream(
            StreamName='user-events',
            ShardCount=1,
            StreamModeDetails={'StreamMode': 'ON_DEMAND'}
        )
    except ClientError:
        print("  Stream already exists")
    
    print("  Waiting for stream to activate...")
    while True:
        resp = kinesis.describe_stream(StreamName='user-events')
        if resp['StreamDescription']['StreamStatus'] == 'ACTIVE':
            break
        time.sleep(2)
    print("  Stream active")

def create_dynamodb_tables(dynamodb):
    """Create DynamoDB tables"""
    print("🗄️  Creating DynamoDB tables")
    
    # Main state table
    try:
        dynamodb.create_table(
            TableName='narrative-state',
            AttributeDefinitions=[
                {'AttributeName': 'pk', 'AttributeType': 'S'},
                {'AttributeName': 'sk', 'AttributeType': 'S'},
                {'AttributeName': 'gsi1pk', 'AttributeType': 'S'},
                {'AttributeName': 'gsi1sk', 'AttributeType': 'S'},
            ],
            KeySchema=[
                {'AttributeName': 'pk', 'KeyType': 'HASH'},
                {'AttributeName': 'sk', 'KeyType': 'RANGE'},
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'GSI1',
                'KeySchema': [
                    {'AttributeName': 'gsi1pk', 'KeyType': 'HASH'},
                    {'AttributeName': 'gsi1sk', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }],
            BillingMode='PAY_PER_REQUEST'
        )
    except ClientError:
        print("  Table 'narrative-state' already exists")
    
    # User preferences table
    try:
        dynamodb.create_table(
            TableName='narrative-preferences',
            AttributeDefinitions=[{'AttributeName': 'user_id', 'AttributeType': 'S'}],
            KeySchema=[{'AttributeName': 'user_id', 'KeyType': 'HASH'}],
            BillingMode='PAY_PER_REQUEST'
        )
    except ClientError:
        print("  Table 'narrative-preferences' already exists")

def create_lambda_function(lambda_client):
    """Create Lambda function"""
    print("⚡ Creating Lambda function: narrative-generator")
    
    # Create zip with lambda code
    lambda_file = Path(__file__).parent / 'processor' / 'lambda_function.py'
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "lambda_package.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(lambda_file, 'lambda_function.py')
        
        try:
            lambda_client.create_function(
                FunctionName='narrative-generator',
                Runtime='python3.11',
                Role='arn:aws:iam::000000000000:role/lambda-role',
                Handler='lambda_function.lambda_handler',
                Code={'ZipFile': open(zip_path, 'rb').read()},
                Environment={
                    'Variables': {
                        'TABLE_NAME': 'narrative-state',
                        'BUCKET_NAME': 'narrative-store',
                        'STREAM_NAME': 'user-events'
                    }
                }
            )
        except ClientError:
            print("  Function already exists")

def create_eventbridge_schedule(scheduler):
    """Create EventBridge schedule"""
    print("⏰ Creating EventBridge schedule: daily-narrative")
    try:
        scheduler.create_schedule(
            Name='daily-narrative',
            ScheduleExpression='cron(30 22 * * ? *)',
            FlexibleTimeWindow={'Mode': 'OFF'},
            Target={
                'Arn': 'arn:aws:lambda:us-east-1:000000000000:function:narrative-generator',
                'RoleArn': 'arn:aws:iam::000000000000:role/scheduler-role',
                'Input': '{"action": "generate_daily_narrative"}'
            }
        )
    except ClientError:
        print("  Schedule already exists")

def create_iam_role(iam):
    """Create IAM role (mock for emulator)"""
    print("🔐 Setting up IAM roles (mock)")
    try:
        iam.create_role(
            RoleName='lambda-role',
            AssumeRolePolicyDocument='''{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }'''
        )
    except ClientError:
        print("  Role already exists")

def create_kinesis_trigger(lambda_client):
    """Set up Kinesis trigger for Lambda"""
    print("🔌 Setting up Kinesis trigger")
    try:
        lambda_client.create_event_source_mapping(
            FunctionName='narrative-generator',
            EventSourceArn='arn:aws:kinesis:us-east-1:000000000000:stream/user-events',
            StartingPosition='LATEST'
        )
    except ClientError:
        print("  Trigger already exists")

def main():
    load_env()
    wait_for_emulator()
    
    print(f"{GREEN}🚀 Starting Narrative Engine Infrastructure Setup{NC}\n")
    print(f"{GREEN}📦 Creating resources...{NC}\n")
    
    # create_s3_bucket(get_client('s3'))
    # create_kinesis_stream(get_client('kinesis'))
    # create_dynamodb_tables(get_client('dynamodb'))
    create_lambda_function(get_client('lambda'))
    create_eventbridge_schedule(get_client('scheduler'))
    create_iam_role(get_client('iam'))
    create_kinesis_trigger(get_client('lambda'))
    
    print(f"\n{GREEN}✅ Infrastructure setup complete!{NC}\n")
    print(f"{GREEN}📋 Resource Summary:{NC}")
    print("  • S3 Bucket:          s3://narrative-store")
    print("  • Kinesis Stream:     user-events")
    print("  • DynamoDB Tables:    narrative-state, narrative-preferences")
    print("  • Lambda Function:    narrative-generator")
    print("  • Schedule:           daily-narrative (10:30 PM daily)")
    print(f"\n{YELLOW}💡 Next Steps:{NC}")
    print("  1. Run: docker-compose up -d")
    print("  2. Test setup: ./scripts/health_check.sh")
    print("  3. Deploy Lambda code: ./infrastructure/deploy_lambda.sh")

if __name__ == '__main__':
    main()