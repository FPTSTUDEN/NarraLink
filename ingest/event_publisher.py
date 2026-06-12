import boto3
import json
from datetime import datetime

client = boto3.client('kinesis', endpoint_url='http://localhost:4566')
# Dummy credentials for emulator
session = boto3.Session(aws_access_key_id='test', aws_secret_access_key='test')

def publish_event(event_type, data):
    client.put_record(
        StreamName='user-events',
        Data=json.dumps({
            'type': event_type,  # 'photo', 'song', 'notification', etc.
            'data': data,
            'timestamp': datetime.now().isoformat()
        }),
        PartitionKey='user-123'  # Your user ID
    )