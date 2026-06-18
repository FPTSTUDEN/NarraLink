#!/usr/bin/env python3
"""Complete infrastructure setup for Personal Narrative Engine."""

import boto3
import json
import time
import zipfile
import tempfile
import os
from pathlib import Path
from botocore.exceptions import ClientError
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
ENDPOINT_URL = os.getenv('AWS_ENDPOINT_URL', 'http://localhost:4566')
REGION = os.getenv('AWS_REGION', 'us-east-1')
ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID', 'test')
SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')

# Resource names
S3_BUCKET = os.getenv('BUCKET_NAME', 'narrative-store')
KINESIS_STREAM = os.getenv('STREAM_NAME', 'user-events')
DYNAMODB_TABLE = os.getenv('TABLE_NAME', 'narrative-state')
DYNAMODB_PREFS = 'narrative-preferences'
LAMBDA_NAME = 'narrative-generator'
BEDROCK_LAMBDA_NAME = 'narrative-bedrock-generator'

class NarrativeInfrastructure:
    def __init__(self):
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            region_name=REGION
        )
        
        self.s3 = session.client('s3', endpoint_url=ENDPOINT_URL)
        self.kinesis = session.client('kinesis', endpoint_url=ENDPOINT_URL)
        self.dynamodb = session.client('dynamodb', endpoint_url=ENDPOINT_URL)
        self.lambda_client = session.client('lambda', endpoint_url=ENDPOINT_URL)
        self.iam = session.client('iam', endpoint_url=ENDPOINT_URL)
        
        logger.info(f"Connected to {ENDPOINT_URL}")
    
    def create_s3_bucket(self):
        """Create S3 bucket with versioning and encryption"""
        try:
            self.s3.head_bucket(Bucket=S3_BUCKET)
            logger.info(f"S3 bucket '{S3_BUCKET}' exists")
            return True
        except ClientError:
            pass
        
        self.s3.create_bucket(Bucket=S3_BUCKET)
        self.s3.put_bucket_versioning(Bucket=S3_BUCKET, VersioningConfiguration={'Status': 'Enabled'})
        self.s3.put_bucket_encryption(
            Bucket=S3_BUCKET,
            ServerSideEncryptionConfiguration={
                'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]
            }
        )
        logger.info(f"✓ Created S3 bucket: {S3_BUCKET}")
        return True
    
    def create_kinesis_stream(self):
        """Create Kinesis data stream"""
        try:
            if KINESIS_STREAM in self.kinesis.list_streams().get('StreamNames', []):
                logger.info(f"Kinesis stream '{KINESIS_STREAM}' exists")
                return True
            
            self.kinesis.create_stream(
                StreamName=KINESIS_STREAM,
                ShardCount=1,
                StreamModeDetails={'StreamMode': 'ON_DEMAND'}
            )
            
            # Wait for active
            while self.kinesis.describe_stream(StreamName=KINESIS_STREAM)['StreamDescription']['StreamStatus'] != 'ACTIVE':
                time.sleep(2)
            
            logger.info(f"✓ Created Kinesis stream: {KINESIS_STREAM}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Kinesis stream: {e}")
            return False
    
    def create_dynamodb_tables(self):
        """Create DynamoDB tables"""
        tables = {
            DYNAMODB_TABLE: {
                'AttributeDefinitions': [
                    {'AttributeName': 'pk', 'AttributeType': 'S'},
                    {'AttributeName': 'sk', 'AttributeType': 'S'},
                    {'AttributeName': 'gsi1pk', 'AttributeType': 'S'},
                    {'AttributeName': 'gsi1sk', 'AttributeType': 'S'}
                ],
                'KeySchema': [
                    {'AttributeName': 'pk', 'KeyType': 'HASH'},
                    {'AttributeName': 'sk', 'KeyType': 'RANGE'}
                ],
                'GlobalSecondaryIndexes': [{
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'gsi1pk', 'KeyType': 'HASH'},
                        {'AttributeName': 'gsi1sk', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }]
            },
            DYNAMODB_PREFS: {
                'AttributeDefinitions': [{'AttributeName': 'user_id', 'AttributeType': 'S'}],
                'KeySchema': [{'AttributeName': 'user_id', 'KeyType': 'HASH'}]
            }
        }
        
        for table_name, schema in tables.items():
            try:
                self.dynamodb.describe_table(TableName=table_name)
                logger.info(f"DynamoDB table '{table_name}' exists")
            except ClientError:
                self.dynamodb.create_table(TableName=table_name, **schema, BillingMode='PAY_PER_REQUEST')
                # Wait for active
                while self.dynamodb.describe_table(TableName=table_name)['Table']['TableStatus'] != 'ACTIVE':
                    time.sleep(2)
                logger.info(f"✓ Created DynamoDB table: {table_name}")
        
        return True
    
    def create_lambda_function(self):
        """Create Lambda from external file"""
        try:
            # Check if external lambda file exists
            lambda_file = Path(__file__).parent / 'processor' / 'lambda_function.py'
            if not lambda_file.exists():
                logger.error(f"lambda_function.py not found at {lambda_file}")
                return False
            
            # Create deployment package
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False) as tmp:
                with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(lambda_file, 'lambda_function.py')
                zip_path = tmp.name
            
            # Create IAM role (mock for localstack)
            try:
                self.iam.create_role(
                    RoleName='lambda-role',
                    AssumeRolePolicyDocument=json.dumps({
                        'Version': '2012-10-17',
                        'Statement': [{
                            'Effect': 'Allow',
                            'Principal': {'Service': 'lambda.amazonaws.com'},
                            'Action': 'sts:AssumeRole'
                        }]
                    })
                )
            except ClientError:
                pass
            
            # Create or update function
            try:
                self.lambda_client.get_function(FunctionName=LAMBDA_NAME)
                with open(zip_path, 'rb') as f:
                    self.lambda_client.update_function_code(FunctionName=LAMBDA_NAME, ZipFile=f.read())
                logger.info(f"✓ Updated Lambda function: {LAMBDA_NAME}")
            except ClientError:
                with open(zip_path, 'rb') as f:
                    self.lambda_client.create_function(
                        FunctionName=LAMBDA_NAME,
                        Runtime='python3.11',
                        Role='arn:aws:iam::000000000000:role/lambda-role',
                        Handler='lambda_function.lambda_handler',
                        Code={'ZipFile': f.read()},
                        Environment={'Variables': {
                            'TABLE_NAME': DYNAMODB_TABLE,
                            'BUCKET_NAME': S3_BUCKET,
                            'STREAM_NAME': KINESIS_STREAM,
                            'USE_MOCK_AI': 'true',
                            'AWS_ENDPOINT_URL': ENDPOINT_URL
                        }},
                        Timeout=300,
                        MemorySize=512
                    )
                logger.info(f"✓ Created Lambda function: {LAMBDA_NAME}")
            
            os.unlink(zip_path)
            return True
        except Exception as e:
            logger.error(f"Failed to create Lambda: {e}")
            return False
    
    def create_event_source_mapping(self):
        """Create Kinesis to Lambda trigger"""
        try:
            stream_arn = self.kinesis.describe_stream(StreamName=KINESIS_STREAM)['StreamDescription']['StreamARN']
            
            # Check existing mappings
            mappings = self.lambda_client.list_event_source_mappings(
                FunctionName=LAMBDA_NAME,
                EventSourceArn=stream_arn
            )
            
            if mappings.get('EventSourceMappings'):
                logger.info(f"Event source mapping exists: {mappings['EventSourceMappings'][0]['UUID']}")
                return True
            
            response = self.lambda_client.create_event_source_mapping(
                FunctionName=LAMBDA_NAME,
                EventSourceArn=stream_arn,
                StartingPosition='LATEST',
                BatchSize=100,
                Enabled=True
            )
            logger.info(f"✓ Created Kinesis → Lambda trigger: {response['UUID']}")
            return True
        except Exception as e:
            logger.error(f"Failed to create mapping: {e}")
            return False
    
    def test_infrastructure(self):
        """Quick infrastructure test"""
        tests = [
            ("S3 bucket", lambda: self.s3.head_bucket(Bucket=S3_BUCKET)),
            ("Kinesis stream", lambda: self.kinesis.describe_stream(StreamName=KINESIS_STREAM)),
            ("DynamoDB tables", lambda: self.dynamodb.describe_table(TableName=DYNAMODB_TABLE)),
            ("Lambda function", lambda: self.lambda_client.get_function(FunctionName=LAMBDA_NAME))
        ]
        
        logger.info("\n" + "="*50)
        logger.info("TESTING INFRASTRUCTURE")
        logger.info("="*50)
        
        all_passed = True
        for name, test_func in tests:
            try:
                test_func()
                logger.info(f"✓ {name} is accessible")
            except Exception as e:
                logger.error(f"✗ {name} failed: {e}")
                all_passed = False
        
        if all_passed:
            logger.info("\n✅ All tests passed!")
        return all_passed
    

    def create_bedrock_lambda(self):
        """Create separate Lambda for Bedrock narrative generation"""
        try:
            lambda_file = Path(__file__).parent / 'processor' / 'lambda_bedrock_narrative.py'
            if not lambda_file.exists():
                logger.error("lambda_bedrock_narrative.py not found")
                return False
            
            # Create deployment package
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False) as tmp:
                with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(lambda_file, 'lambda_function.py')
                zip_path = tmp.name
            
            # Create function with higher memory for Bedrock
            try:
                self.lambda_client.get_function(FunctionName=BEDROCK_LAMBDA_NAME)
                logger.info("✓ Bedrock narrative generator Lambda already exists")
            except self.lambda_client.exceptions.ResourceNotFoundException:
                with open(zip_path, 'rb') as f:
                    self.lambda_client.create_function(
                        FunctionName='narrative-bedrock-generator',
                        Runtime='python3.11',
                        Role='arn:aws:iam::000000000000:role/lambda-role',
                        Handler='lambda_function.lambda_handler',
                        Code={'ZipFile': f.read()},
                        Environment={'Variables': {
                            'TABLE_NAME': DYNAMODB_TABLE,
                            'BUCKET_NAME': S3_BUCKET,
                            'BEDROCK_MODEL_ID': 'anthropic.claude-3-sonnet-20240229-v1:0',
                            'STORY_TONE': 'reflective'
                        }},
                        Timeout=600,  # 10 minutes for Bedrock
                        MemorySize=1769  # Optimal for ML workloads
                    )
                
                logger.info("✓ Created Bedrock narrative generator Lambda")
            os.unlink(zip_path)
            return True
        except Exception as e:
            logger.error(f"Failed to create Bedrock Lambda: {e}")
            return False
    
    def create_eventbridge_trigger(self):
        """Schedule nightly narrative generation"""
        events = boto3.client('events', endpoint_url=ENDPOINT_URL)
        
        # Create rule for daily trigger at 2 AM
        try:
            events.put_rule(
                Name='daily-narrative-generation',
                ScheduleExpression='cron(0 2 * * ? *)',
                State='ENABLED'
            )
            
            # Add target to trigger Bedrock Lambda
            events.put_targets(
                Rule='daily-narrative-generation',
                Targets=[{
                    'Id': '1',
                    'Arn': f'arn:aws:lambda:{REGION}:000000000000:function:narrative-bedrock-generator',
                    'Input': json.dumps({
                        'action': 'generate_daily',
                        'user_id': 'all-users'  # Will need to iterate through users
                    })
                }]
            )
            
            logger.info("✓ Created EventBridge schedule for daily narratives")
            return True
        except Exception as e:
            logger.warning(f"Could not create EventBridge trigger: {e}")
            return False
    

    def setup_all(self):
        """Run complete setup"""
        logger.info("="*60)
        logger.info("NARRATIVE ENGINE INFRASTRUCTURE SETUP")
        logger.info("="*60)
        
        steps = [
            ("S3 Bucket", self.create_s3_bucket),
            ("Kinesis Stream", self.create_kinesis_stream),
            ("DynamoDB Tables", self.create_dynamodb_tables),
            ("Original Lambda Function", self.create_lambda_function),
            ("Bedrock Lambda Function", self.create_bedrock_lambda),
            ("Event Source Mapping", self.create_event_source_mapping)
            # ,
            # ("EventBridge Trigger", self.create_eventbridge_trigger)
        ]
        
        for name, step in steps:
            logger.info(f"\n📦 Creating {name}...")
            if not step():
                logger.error(f"❌ Failed to create {name}")
                return False
        
        logger.info("\n✅ Setup complete!")
        self.test_infrastructure()
        self.print_summary()
        return True
    
    def print_summary(self):
        """Print resource summary"""
        logger.info("\n📋 RESOURCE SUMMARY")
        logger.info("-" * 40)
        logger.info(f"S3 Bucket:       s3://{S3_BUCKET}")
        logger.info(f"Kinesis Stream:  {KINESIS_STREAM}")
        logger.info(f"DynamoDB Tables: {DYNAMODB_TABLE}, {DYNAMODB_PREFS}")
        logger.info(f"Original Lambda Function: {LAMBDA_NAME}")
        logger.info(f"Bedrock Lambda Function: {BEDROCK_LAMBDA_NAME}")
        logger.info(f"Trigger:         Kinesis → Lambda (ACTIVE)")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Setup Narrative Engine infrastructure')
    parser.add_argument('--test-only', action='store_true', help='Only test existing infrastructure')
    args = parser.parse_args()
    
    infra = NarrativeInfrastructure()
    
    if args.test_only:
        infra.test_infrastructure()
    else:
        infra.setup_all()

if __name__ == "__main__":
    main()