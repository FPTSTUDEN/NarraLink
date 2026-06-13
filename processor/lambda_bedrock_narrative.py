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
STORY_TONE = os.getenv('STORY_TONE', 'reflective')

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
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE_NAME)
    
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
        return {
            'statusCode': 404,
            'body': json.dumps({'error': f'No events for {date}'})
        }
    
    # Generate with Bedrock
    narrative = call_bedrock(user_id, date, events)
    
    # Store narrative
    s3_key = f"narratives/{user_id}/{date}/narrative.md"
    boto3.client('s3').put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=narrative
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Narrative generated',
            's3_key': s3_key,
            'event_count': len(events)
        })
    }

def call_bedrock(user_id: str, date: str, events: List[Dict]) -> str:
    """Call Amazon Bedrock to generate narrative"""
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    
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

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
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

def generate_weekly_narrative(user_id: str) -> Dict:
    """Generate weekly summary"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    return generate_range_narrative(user_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

def generate_range_narrative(user_id: str, start_date: str, end_date: str) -> Dict:
    """Generate narrative for date range"""
    # Implementation similar to daily but aggregates multiple days
    # ... (implementation details)
    pass