#!/usr/bin/env python3
# setup.py
"""
Complete infrastructure setup for Personal Narrative Engine.
Creates all AWS resources: S3, Kinesis, DynamoDB, Lambda, and Event Source Mapping.
"""

import boto3
import json
import time
import os
import sys
import zipfile
import tempfile
from datetime import datetime
from botocore.exceptions import ClientError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
ENDPOINT_URL = os.getenv('AWS_ENDPOINT_URL', 'http://localhost:4566')
REGION = os.getenv('AWS_REGION', 'us-east-1')
ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID', 'test')
SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')

# Resource names
S3_BUCKET_NAME = os.getenv('BUCKET_NAME', 'narrative-store')
KINESIS_STREAM_NAME = os.getenv('STREAM_NAME', 'user-events')
DYNAMODB_TABLE_NAME = os.getenv('TABLE_NAME', 'narrative-state')
DYNAMODB_PREFS_TABLE = 'narrative-preferences'
LAMBDA_FUNCTION_NAME = 'narrative-generator'

class NarrativeInfrastructure:
    """Manages AWS infrastructure setup for Narrative Engine"""
    
    def __init__(self):
        """Initialize AWS clients with local endpoint configuration"""
        self.session = boto3.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            region_name=REGION
        )
        
        # Create clients with endpoint URL
        self.s3 = self.session.client('s3', endpoint_url=ENDPOINT_URL)
        self.kinesis = self.session.client('kinesis', endpoint_url=ENDPOINT_URL)
        self.dynamodb = self.session.client('dynamodb', endpoint_url=ENDPOINT_URL)
        self.lambda_client = self.session.client('lambda', endpoint_url=ENDPOINT_URL)
        self.iam = self.session.client('iam', endpoint_url=ENDPOINT_URL)
        
        logger.info(f"Connected to AWS emulator at {ENDPOINT_URL}")
        logger.info(f"Region: {REGION}")
        
    def create_s3_bucket(self):
        """Create S3 bucket for storing raw events and stories"""
        try:
            # Check if bucket exists
            try:
                self.s3.head_bucket(Bucket=S3_BUCKET_NAME)
                logger.info(f"S3 bucket '{S3_BUCKET_NAME}' already exists")
                return True
            except ClientError:
                pass
            
            # Create bucket
            self.s3.create_bucket(Bucket=S3_BUCKET_NAME)
            logger.info(f"✓ Created S3 bucket: {S3_BUCKET_NAME}")
            
            # Enable versioning
            self.s3.put_bucket_versioning(
                Bucket=S3_BUCKET_NAME,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            logger.info(f"  Enabled versioning for {S3_BUCKET_NAME}")
            
            # Enable encryption
            self.s3.put_bucket_encryption(
                Bucket=S3_BUCKET_NAME,
                ServerSideEncryptionConfiguration={
                    'Rules': [{
                        'ApplyServerSideEncryptionByDefault': {
                            'SSEAlgorithm': 'AES256'
                        }
                    }]
                }
            )
            logger.info(f"  Enabled encryption for {S3_BUCKET_NAME}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create S3 bucket: {e}")
            return False
    
    def create_kinesis_stream(self):
        """Create Kinesis data stream"""
        try:
            # Check if stream exists
            existing_streams = self.kinesis.list_streams()
            if KINESIS_STREAM_NAME in existing_streams.get('StreamNames', []):
                logger.info(f"Kinesis stream '{KINESIS_STREAM_NAME}' already exists")
                
                # Get stream details
                desc = self.kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
                status = desc['StreamDescription']['StreamStatus']
                logger.info(f"  Stream status: {status}")
                return True
            
            # Create stream
            self.kinesis.create_stream(
                StreamName=KINESIS_STREAM_NAME,
                ShardCount=1,
                StreamModeDetails={'StreamMode': 'ON_DEMAND'}
            )
            logger.info(f"✓ Created Kinesis stream: {KINESIS_STREAM_NAME}")
            
            # Wait for stream to become active
            logger.info("  Waiting for stream to become active...")
            while True:
                response = self.kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
                status = response['StreamDescription']['StreamStatus']
                if status == 'ACTIVE':
                    break
                logger.info(f"  Stream status: {status}...")
                time.sleep(2)
            
            logger.info(f"  Stream is ACTIVE")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create Kinesis stream: {e}")
            return False
    
    def create_dynamodb_tables(self):
        """Create DynamoDB tables for state and preferences"""
        try:
            # Create main state table
            try:
                self.dynamodb.describe_table(TableName=DYNAMODB_TABLE_NAME)
                logger.info(f"DynamoDB table '{DYNAMODB_TABLE_NAME}' already exists")
            except ClientError:
                # Create table
                self.dynamodb.create_table(
                    TableName=DYNAMODB_TABLE_NAME,
                    AttributeDefinitions=[
                        {'AttributeName': 'pk', 'AttributeType': 'S'},
                        {'AttributeName': 'sk', 'AttributeType': 'S'},
                        {'AttributeName': 'gsi1pk', 'AttributeType': 'S'},
                        {'AttributeName': 'gsi1sk', 'AttributeType': 'S'}
                    ],
                    KeySchema=[
                        {'AttributeName': 'pk', 'KeyType': 'HASH'},
                        {'AttributeName': 'sk', 'KeyType': 'RANGE'}
                    ],
                    GlobalSecondaryIndexes=[
                        {
                            'IndexName': 'GSI1',
                            'KeySchema': [
                                {'AttributeName': 'gsi1pk', 'KeyType': 'HASH'},
                                {'AttributeName': 'gsi1sk', 'KeyType': 'RANGE'}
                            ],
                            'Projection': {'ProjectionType': 'ALL'}
                        }
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
                logger.info(f"✓ Created DynamoDB table: {DYNAMODB_TABLE_NAME}")
                
                # Wait for table to be active
                logger.info("  Waiting for table to become active...")
                while True:
                    response = self.dynamodb.describe_table(TableName=DYNAMODB_TABLE_NAME)
                    status = response['Table']['TableStatus']
                    if status == 'ACTIVE':
                        break
                    time.sleep(2)
                logger.info(f"  Table is ACTIVE")
            
            # Create preferences table
            try:
                self.dynamodb.describe_table(TableName=DYNAMODB_PREFS_TABLE)
                logger.info(f"DynamoDB table '{DYNAMODB_PREFS_TABLE}' already exists")
            except ClientError:
                self.dynamodb.create_table(
                    TableName=DYNAMODB_PREFS_TABLE,
                    AttributeDefinitions=[
                        {'AttributeName': 'user_id', 'AttributeType': 'S'}
                    ],
                    KeySchema=[
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'}
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
                logger.info(f"✓ Created DynamoDB table: {DYNAMODB_PREFS_TABLE}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create DynamoDB tables: {e}")
            return False
    
    def create_lambda_function(self):
        """Create Lambda function for processing events and generating stories"""
        try:
            # Lambda function code
            lambda_code = self._get_lambda_code()
            
            # Create deployment package
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.zip', delete=False) as tmp_file:
                with zipfile.ZipFile(tmp_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.writestr('lambda_function.py', lambda_code)
                zip_path = tmp_file.name
            
            # Check if function exists
            try:
                self.lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
                logger.info(f"Lambda function '{LAMBDA_FUNCTION_NAME}' already exists")
                
                # Update function code
                with open(zip_path, 'rb') as f:
                    self.lambda_client.update_function_code(
                        FunctionName=LAMBDA_FUNCTION_NAME,
                        ZipFile=f.read()
                    )
                logger.info(f"  Updated Lambda function code")
                
            except ClientError:
                # Create IAM role (mock for emulator)
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
                    pass  # Role might already exist
                
                # Create function
                with open(zip_path, 'rb') as f:
                    self.lambda_client.create_function(
                        FunctionName=LAMBDA_FUNCTION_NAME,
                        Runtime='python3.11',
                        Role='arn:aws:iam::000000000000:role/lambda-role',
                        Handler='lambda_function.lambda_handler',
                        Code={'ZipFile': f.read()},
                        Environment={
                            'Variables': {
                                'TABLE_NAME': DYNAMODB_TABLE_NAME,
                                'BUCKET_NAME': S3_BUCKET_NAME,
                                'STREAM_NAME': KINESIS_STREAM_NAME,
                                'USE_MOCK_AI': 'true',
                                'STORY_TONE': 'reflective',
                                'OUTPUT_FORMAT': 'markdown',
                                'AWS_ENDPOINT_URL': ENDPOINT_URL,
                                'AWS_REGION': REGION
                            }
                        },
                        Timeout=300,  # 5 minutes
                        MemorySize=512
                    )
                logger.info(f"✓ Created Lambda function: {LAMBDA_FUNCTION_NAME}")
            
            # Clean up temp file
            os.unlink(zip_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create Lambda function: {e}")
            return False
    
    def _get_lambda_code(self):
        """Return Lambda function code as string"""
        return '''import json
import os
import boto3
import base64
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import random

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
TABLE_NAME = os.getenv('TABLE_NAME', 'narrative-state')
BUCKET_NAME = os.getenv('BUCKET_NAME', 'narrative-store')
STREAM_NAME = os.getenv('STREAM_NAME', 'user-events')
USE_MOCK_AI = os.getenv('USE_MOCK_AI', 'true').lower() == 'true'
STORY_TONE = os.getenv('STORY_TONE', 'reflective')
ENDPOINT_URL = os.getenv('AWS_ENDPOINT_URL')

def get_client(service):
    """Get AWS client with proper endpoint"""
    if ENDPOINT_URL:
        return boto3.client(service, endpoint_url=ENDPOINT_URL, region_name='us-east-1')
    return boto3.client(service, region_name='us-east-1')

def get_resource(service):
    """Get AWS resource with proper endpoint"""
    if ENDPOINT_URL:
        return boto3.resource(service, endpoint_url=ENDPOINT_URL, region_name='us-east-1')
    return boto3.resource(service, region_name='us-east-1')

dynamodb = get_resource('dynamodb')
s3 = get_client('s3')
table = dynamodb.Table(TABLE_NAME)

def process_kinesis_records(records):
    """Process events from Kinesis"""
    processed = 0
    errors = 0
    
    for record in records:
        try:
            # Decode event data
            encoded_data = record['kinesis']['data']
            decoded_data = base64.b64decode(encoded_data).decode('utf-8')
            event = json.loads(decoded_data)
            
            logger.info(f"Processing event: {event.get('event_id', 'unknown')}")
            
            # Store in DynamoDB
            event_id = event.get('event_id')
            event_type = event.get('type')
            user_id = event.get('user_id', 'unknown')
            timestamp = event.get('timestamp', datetime.now().isoformat())
            data = event.get('data', {})
            date = timestamp[:10]
            
            table.put_item(
                Item={
                    'pk': f"user::{user_id}",
                    'sk': f"event::{timestamp}",
                    'gsi1pk': f"day::{date}",
                    'gsi1sk': timestamp,
                    'event_type': event_type,
                    'event_id': event_id,
                    'event_data': json.dumps(data)
                }
            )
            
            # Store in S3
            s3_key = f"raw/user={user_id}/year={date[:4]}/month={date[5:7]}/day={date[8:10]}/{event_id}.json"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=json.dumps(event, indent=2)
            )
            
            processed += 1
            
        except Exception as e:
            logger.error(f"Error processing record: {e}")
            errors += 1
    
    return {'processed': processed, 'errors': errors}

def generate_story(user_id, date=None):
    """Generate a story from events"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Query events from DynamoDB
    response = table.query(
        IndexName='GSI1',
        KeyConditionExpression="gsi1pk = :pk",
        ExpressionAttributeValues={":pk": f"day::{date}"}
    )
    
    events = []
    for item in response.get('Items', []):
        if item['pk'] == f"user::{user_id}":
            events.append({
                'timestamp': item['sk'].replace('event::', ''),
                'type': item['event_type'],
                'data': json.loads(item.get('event_data', '{}'))
            })
    
    if not events:
        return f"No events found for {date}"
    
    events.sort(key=lambda x: x['timestamp'])
    
    # Generate simple story
    story = f"# Daily Narrative - {date}\\n\\n"
    story += f"Today you had {len(events)} digital moments.\\n\\n"
    
    # Group events by type
    event_counts = defaultdict(int)
    for event in events:
        event_counts[event['type']] += 1
    
    for event_type, count in event_counts.items():
        story += f"- {count} {event_type} event(s)\\n"
    
    story += "\\n*Generated by Narrative Engine*"
    
    # Save story
    local_path = f"/tmp/story_{date}.md"
    with open(local_path, 'w') as f:
        f.write(story)
    
    return story

def lambda_handler(event, context):
    """Main Lambda handler"""
    logger.info(f"Lambda invoked")
    
    # Check if this is a Kinesis trigger
    if 'Records' in event and event['Records']:
        first_record = event['Records'][0]
        if 'kinesis' in first_record:
            result = process_kinesis_records(event['Records'])
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
    
    # Handle direct invocation
    action = event.get('action', 'generate_daily_narrative')
    user_id = event.get('user_id', 'default-user')
    
    if action == 'generate_daily_narrative':
        date = event.get('date', datetime.now().strftime("%Y-%m-%d"))
        story = generate_story(user_id, date)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Story generated',
                'story': story,
                'date': date
            })
        }
    
    return {'statusCode': 400, 'body': json.dumps({'error': 'Unknown action'})}
'''
    
    def create_event_source_mapping(self):
        """Create Kinesis to Lambda event source mapping"""
        try:
            # Get stream ARN
            stream_desc = self.kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
            stream_arn = stream_desc['StreamDescription']['StreamARN']
            
            # Check if mapping already exists
            existing_mappings = self.lambda_client.list_event_source_mappings(
                FunctionName=LAMBDA_FUNCTION_NAME,
                EventSourceArn=stream_arn
            )
            
            if existing_mappings.get('EventSourceMappings'):
                mapping_id = existing_mappings['EventSourceMappings'][0]['UUID']
                logger.info(f"Event source mapping already exists: {mapping_id}")
                logger.info(f"  State: {existing_mappings['EventSourceMappings'][0]['State']}")
                return True
            
            # Create mapping
            response = self.lambda_client.create_event_source_mapping(
                FunctionName=LAMBDA_FUNCTION_NAME,
                EventSourceArn=stream_arn,
                StartingPosition='LATEST',
                BatchSize=100,
                MaximumRetryAttempts=3,
                Enabled=True
            )
            
            mapping_id = response['UUID']
            logger.info(f"✓ Created Kinesis → Lambda event source mapping: {mapping_id}")
            logger.info(f"  State: {response['State']}")
            
            # Wait for mapping to become enabled
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create event source mapping: {e}")
            return False
    
    def test_infrastructure(self):
        """Test the complete infrastructure setup"""
        logger.info("\n" + "="*50)
        logger.info("TESTING INFRASTRUCTURE")
        logger.info("="*50)
        
        # Test 1: S3 bucket
        try:
            self.s3.head_bucket(Bucket=S3_BUCKET_NAME)
            logger.info("✓ S3 bucket is accessible")
        except Exception as e:
            logger.error(f"✗ S3 bucket test failed: {e}")
            return False
        
        # Test 2: Kinesis stream
        try:
            desc = self.kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
            status = desc['StreamDescription']['StreamStatus']
            logger.info(f"✓ Kinesis stream is {status}")
        except Exception as e:
            logger.error(f"✗ Kinesis stream test failed: {e}")
            return False
        
        # Test 3: DynamoDB tables
        try:
            self.dynamodb.describe_table(TableName=DYNAMODB_TABLE_NAME)
            logger.info(f"✓ DynamoDB table '{DYNAMODB_TABLE_NAME}' exists")
            
            self.dynamodb.describe_table(TableName=DYNAMODB_PREFS_TABLE)
            logger.info(f"✓ DynamoDB table '{DYNAMODB_PREFS_TABLE}' exists")
        except Exception as e:
            logger.error(f"✗ DynamoDB tables test failed: {e}")
            return False
        
        # Test 4: Lambda function
        try:
            func = self.lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
            logger.info(f"✓ Lambda function '{LAMBDA_FUNCTION_NAME}' exists")
            
            # Check event source mapping
            stream_arn = desc['StreamDescription']['StreamARN']
            mappings = self.lambda_client.list_event_source_mappings(
                FunctionName=LAMBDA_FUNCTION_NAME,
                EventSourceArn=stream_arn
            )
            
            if mappings.get('EventSourceMappings'):
                logger.info("✓ Kinesis → Lambda trigger is configured")
            else:
                logger.warning("⚠ No Kinesis → Lambda trigger found")
                
        except Exception as e:
            logger.error(f"✗ Lambda function test failed: {e}")
            return False
        
        logger.info("\n✅ All infrastructure tests passed!")
        return True
    
    def setup_all(self):
        """Run complete infrastructure setup"""
        logger.info("="*60)
        logger.info("NARRATIVE ENGINE INFRASTRUCTURE SETUP")
        logger.info("="*60)
        logger.info(f"Endpoint: {ENDPOINT_URL}")
        logger.info(f"Region: {REGION}")
        logger.info("")
        
        steps = [
            ("S3 Bucket", self.create_s3_bucket),
            ("Kinesis Stream", self.create_kinesis_stream),
            ("DynamoDB Tables", self.create_dynamodb_tables),
            ("Lambda Function", self.create_lambda_function),
            ("Event Source Mapping", self.create_event_source_mapping)
        ]
        
        success = True
        for step_name, step_func in steps:
            logger.info(f"\n📦 Creating {step_name}...")
            if step_func():
                logger.info(f"✅ {step_name} created successfully")
            else:
                logger.error(f"❌ Failed to create {step_name}")
                success = False
                break
        
        if success:
            logger.info("\n" + "="*60)
            logger.info("✅ INFRASTRUCTURE SETUP COMPLETE!")
            logger.info("="*60)
            
            # Run tests
            self.test_infrastructure()
            
            # Print summary
            self.print_summary()
        else:
            logger.error("\n❌ Infrastructure setup failed")
        
        return success
    
    def print_summary(self):
        """Print resource summary"""
        logger.info("\n📋 RESOURCE SUMMARY")
        logger.info("-" * 40)
        logger.info(f"S3 Bucket:          s3://{S3_BUCKET_NAME}")
        logger.info(f"Kinesis Stream:     {KINESIS_STREAM_NAME}")
        logger.info(f"DynamoDB Tables:    {DYNAMODB_TABLE_NAME}, {DYNAMODB_PREFS_TABLE}")
        logger.info(f"Lambda Function:    {LAMBDA_FUNCTION_NAME}")
        logger.info(f"Kinesis Trigger:    ACTIVE (auto-invokes Lambda)")
        logger.info("\n💡 NEXT STEPS:")
        logger.info("1. Send test events: python scripts/send_test_events.py")
        logger.info("2. Check Lambda logs: docker-compose logs aws-emulator | grep -i lambda")
        logger.info("3. Generate story: aws lambda invoke --function-name narrative-generator \\")
        logger.info("                     --payload '{\"action\":\"generate_daily_narrative\"}' response.json")
        logger.info("4. View stories: cat stories/output/daily_*.md")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup Narrative Engine infrastructure')
    parser.add_argument('--destroy', action='store_true', help='Destroy all resources')
    parser.add_argument('--test-only', action='store_true', help='Only test existing infrastructure')
    
    args = parser.parse_args()
    
    infra = NarrativeInfrastructure()
    
    if args.destroy:
        logger.info("Destroy mode not implemented yet")
        # TODO: Implement resource deletion
        return
    
    if args.test_only:
        infra.test_infrastructure()
        return
    
    # Run full setup
    infra.setup_all()

if __name__ == "__main__":
    main()