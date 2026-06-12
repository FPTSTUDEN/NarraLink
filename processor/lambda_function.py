# lambda_function.py
import json


def handler(event, context):
    # events arrive from Kinesis
    for record in event['Records']:
        raw_event = json.loads(record['kinesis']['data'])
        store_raw_event(raw_event)  # To S3
        update_daily_context(raw_event)  # To DynamoDB
    
    # End of day trigger (time-based or manual)
    if day_has_ended():
        context = fetch_daily_context()
        story = generate_story_with_bedrock(context)
        return publish_journal(story)