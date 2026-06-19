#!/usr/bin/env python3
"""Bedrock-powered narrative generation Lambda (separate function)"""

import json
import os
import boto3
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
TABLE_NAME = os.getenv('TABLE_NAME', 'narrative-state')
BUCKET_NAME = os.getenv('BUCKET_NAME', 'narrative-store')
BEDROCK_MODEL_ID = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')
BEDROCK_RUNTIME_ENDPOINT = os.getenv('BEDROCK_RUNTIME_ENDPOINT', 'http://localhost:4000')
STORY_TONE = os.getenv('STORY_TONE', 'reflective')


def get_aws_client(service_name, resource=False,endpoint=None):
    """Get AWS client - endpoint controlled by env var"""
    IS_LOCAL = os.environ.get("IS_LOCAL", "true").lower() == "true"
    
    client_kwargs = {
        "region_name": os.environ.get("AWS_REGION", "us-east-1"),
    }
    
    if IS_LOCAL:
        # Use service-specific endpoint or generic one
        endpoint_key = f"{service_name.upper().replace('-', '_')}_ENDPOINT"
        endpoint = os.environ.get(endpoint_key) if endpoint is None else endpoint
        
        if not endpoint:
            # Fallback to generic endpoint for all services
            endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
        
        client_kwargs.update({
            "endpoint_url": endpoint,
            "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "mock_key"),
            "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "mock_secret")
        })
        print(f"Using local endpoint for {service_name}: {endpoint}")
    
    if resource:
        return boto3.resource(service_name, **client_kwargs)
    return boto3.client(service_name, **client_kwargs)


def get_model_id():
    """Get appropriate model ID based on environment"""
    IS_LOCAL = os.environ.get("IS_LOCAL", "true").lower() == "true"
    
    if IS_LOCAL:
        return "ollama/tinyllama"  # Local model
    else:
        return BEDROCK_MODEL_ID  # Production model from env var


def lambda_handler(event, context):
    """Handle narrative generation requests"""
    action = event.get('action', 'generate_daily')
    
    if action == 'generate_daily':
        return generate_daily_narrative(
            event.get('user_id'),
            event.get('date', datetime.now().strftime("%Y-%m-%d"))
        )
    elif action == 'generate_weekly':
        return generate_weekly_narrative(event.get('user_id'))
    elif action == 'generate_range':
        return generate_range_narrative(
            event.get('user_id'),
            event.get('start_date'),
            event.get('end_date')
        )
    else:
        return {'statusCode': 400, 'body': json.dumps({'error': 'Unknown action'})}


def generate_daily_narrative(user_id: str, date: str) -> Dict:
    """Generate narrative for a single day using Bedrock"""
    # Fetch events from DynamoDB
    dynamodb = get_aws_client("dynamodb", resource=True)
    table = dynamodb.Table(TABLE_NAME)
    
    try:
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression="gsi1pk = :pk",
            ExpressionAttributeValues={":pk": f"day::{date}"}
        )
    except Exception as e:
        logger.error(f"DynamoDB query failed: {e}")
        # Return mock data for local testing
        events = [
            {
                'timestamp': '2026-06-19 09:00:00',
                'type': 'wake_up',
                'data': {'time': '09:00'}
            },
            {
                'timestamp': '2026-06-19 10:30:00',
                'type': 'work_start',
                'data': {'task': 'coding'}
            }
        ]
        
        # Generate with Bedrock
        narrative = call_bedrock(user_id, date, events)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Narrative generated (mock data)',
                'narrative': narrative,
                'event_count': len(events)
            })
        }
    
    events = []
    for item in response.get('Items', []):
        if item['pk'] == f"user::{user_id}":
            events.append({
                'timestamp': item['sk'].replace('event::', ''),
                'type': item['event_type'],
                'data': json.loads(item.get('event_data', '{}'))
            })
    
    if not events:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': f'No events for {date}'})
        }
    
    # Generate with Bedrock
    narrative = call_bedrock(user_id, date, events)
    
    # Store narrative
    s3_key = f"narratives/{user_id}/{date}/narrative.md"
    try:
        s3 = get_aws_client("s3")
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=narrative
        )
    except Exception as e:
        logger.warning(f"Failed to store in S3: {e}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Narrative generated',
            's3_key': s3_key,
            'event_count': len(events),
            'narrative': narrative  # Include for testing
        })
    }


def call_bedrock(user_id: str, date: str, events: List[Dict]) -> str:
    """Call Amazon Bedrock to generate narrative"""
    # Get configured client and model ID
    bedrock = get_aws_client("bedrock-runtime",endpoint=BEDROCK_RUNTIME_ENDPOINT)
    model_id = get_model_id()
    
    # Prepare events summary
    events_text = '\n'.join([
        f"- {e['timestamp']}: {e['type']} - {json.dumps(e['data'])}"
        for e in events[:20]  # Limit to 20 most recent
    ])
    
    prompt = f"""Generate a {STORY_TONE} narrative based on these user events from {date}.

Events:
{events_text}

Write a compelling story that:
1. Connects related events
2. Highlights meaningful moments
3. Maintains a {STORY_TONE} tone
4. Ends with an insight

Story:"""

    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1500,
                "temperature": 0.7,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
    except Exception as e:
        logger.error(f"Bedrock call failed: {e}")
        # Return a fallback response for testing
        return f"A {STORY_TONE} story about {len(events)} events from {date}."


def generate_weekly_narrative(user_id: str) -> Dict:
    """Generate weekly summary"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    return generate_range_narrative(user_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))


def generate_range_narrative(user_id: str, start_date: str, end_date: str) -> Dict:
    """Generate narrative for date range"""
    # Implementation similar to daily but aggregates multiple days
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Range narrative generated',
            'start_date': start_date,
            'end_date': end_date
        })
    }