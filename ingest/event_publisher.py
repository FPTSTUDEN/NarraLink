#!/usr/bin/env python3
#ingest/event_publisher.py
"""
Event ingestion library for sending user events to Kinesis.
Supports local development with AWS emulator.
"""

import boto3
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventType(Enum):
    PHOTO = "photo"
    FILE = "file"
    SONG = "song"
    NOTIFICATION = "notification"
    EMAIL = "email"
    CALENDAR = "calendar"
    MESSAGE = "message"
    BROWSER = "browser"
    APP_USAGE = "app_usage"
    LOCATION = "location"
    SCREEN_TIME = "screen_time"

@dataclass
class NarrativeEvent:
    """Base event structure for all narrative events"""
    type: EventType
    user_id: str
    timestamp: str
    data: Dict[str, Any]
    event_id: str = None
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if isinstance(self.type, EventType):
            self.type = self.type.value
    
    def to_json(self) -> str:
        """Convert to JSON string for Kinesis"""
        return json.dumps(asdict(self), default=str)

class EventPublisher:
    """Publishes events to Kinesis stream"""
    
    def __init__(self, stream_name: str = "user-events", endpoint_url: str = None):
        self.stream_name = stream_name
        
        # Use environment variables with fallbacks
        endpoint = endpoint_url or os.getenv('AWS_ENDPOINT_URL') or 'http://localhost:4566'  # Default local endpoint
        region = os.getenv('AWS_REGION', 'us-east-1')
        access_key = os.getenv('AWS_ACCESS_KEY_ID', 'test')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')
        
        # Configure AWS client for local emulator
        config = {
            'region_name': region,
            'aws_access_key_id': access_key,
            'aws_secret_access_key': secret_key,
            'use_ssl': False,
            'verify': False
        }
        
        # Add endpoint if specified (for local emulator)
        if endpoint:
            config['endpoint_url'] = endpoint
            logger.info(f"Using custom endpoint: {endpoint}")
        
        # Disable botocore's credential validation for local testing
        if endpoint and 'localhost' in endpoint:
            os.environ['AWS_SECURITY_TOKEN'] = 'test'
            os.environ['AWS_SESSION_TOKEN'] = 'test'
        
        try:
            self.kinesis = boto3.client('kinesis', **config)
            logger.info(f"Initialized EventPublisher with stream: {stream_name}, endpoint: {endpoint or 'AWS'}")
        except Exception as e:
            logger.error(f"Failed to initialize Kinesis client: {e}")
            raise
        
    def publish_event(self, event: NarrativeEvent) -> Dict[str, Any]:
        """Publish a single event to Kinesis"""
        try:
            # Verify stream exists before publishing
            try:
                self.kinesis.describe_stream(StreamName=self.stream_name)
            except Exception as e:
                logger.warning(f"Stream {self.stream_name} may not exist: {e}")
                # Try to create stream if it doesn't exist (for local dev)
                if 'localhost' in os.getenv('AWS_ENDPOINT_URL', ''):
                    try:
                        self.kinesis.create_stream(
                            StreamName=self.stream_name,
                            ShardCount=1
                        )
                        logger.info(f"Created stream {self.stream_name}")
                        # Wait a bit for stream to be ready
                        import time
                        time.sleep(2)
                    except:
                        pass
            
            response = self.kinesis.put_record(
                StreamName=self.stream_name,
                Data=event.to_json(),
                PartitionKey=event.user_id
            )
            logger.debug(f"Published event {event.event_id} of type {event.type}")
            return response
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            logger.error(f"Event data: {event.to_json()}")
            raise
    
    def publish_batch(self, events: List[NarrativeEvent]) -> List[Dict[str, Any]]:
        """Publish multiple events in a batch"""
        responses = []
        for event in events:
            responses.append(self.publish_event(event))
        return responses

class EventBuilder:
    """Helper class to build common event types"""
    
    @staticmethod
    def photo_event(user_id: str, filename: str, location: str = None, 
                    camera: str = None, tags: List[str] = None) -> NarrativeEvent:
        return NarrativeEvent(
            type=EventType.PHOTO,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "filename": filename,
                "location": location or "unknown",
                "camera": camera or "unknown",
                "tags": tags or []
            }
        )
    
    @staticmethod
    def file_event(user_id: str, filename: str, file_type: str, 
                   size_bytes: int, path: str = None) -> NarrativeEvent:
        return NarrativeEvent(
            type=EventType.FILE,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "filename": filename,
                "file_type": file_type,
                "size_bytes": size_bytes,
                "path": path or "/",
                "action": "created"  # or modified, deleted
            }
        )
    
    @staticmethod
    def song_event(user_id: str, title: str, artist: str, 
                   album: str = None, duration: int = None,
                   platform: str = "unknown") -> NarrativeEvent:
        return NarrativeEvent(
            type=EventType.SONG,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "title": title,
                "artist": artist,
                "album": album,
                "duration_seconds": duration,
                "platform": platform
            }
        )
    
    @staticmethod
    def notification_event(user_id: str, app: str, title: str, 
                          body: str = None, priority: str = "normal") -> NarrativeEvent:
        return NarrativeEvent(
            type=EventType.NOTIFICATION,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "app": app,
                "title": title,
                "body": body,
                "priority": priority,
                "action_taken": None  # clicked, dismissed, ignored
            }
        )
    
    @staticmethod
    def email_event(user_id: str, subject: str, from_addr: str, 
                    importance: str = "normal", snippet: str = None) -> NarrativeEvent:
        return NarrativeEvent(
            type=EventType.EMAIL,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "subject": subject,
                "from": from_addr,
                "importance": importance,
                "snippet": snippet or subject[:50]
            }
        )
    
    @staticmethod
    def calendar_event(user_id: str, title: str, start_time: str, 
                       end_time: str, location: str = None,
                       attendees: List[str] = None) -> NarrativeEvent:
        return NarrativeEvent(
            type=EventType.CALENDAR,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "attendees": attendees or []
            }
        )
    
    @staticmethod
    def message_event(user_id: str, platform: str, sender: str, 
                      content: str, is_group: bool = False) -> NarrativeEvent:
        return NarrativeEvent(
            type=EventType.MESSAGE,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "platform": platform,  # WhatsApp, iMessage, Slack, etc.
                "sender": sender,
                "content": content[:200],  # Truncate for privacy
                "is_group": is_group,
                "length": len(content)
            }
        )
    
    @staticmethod
    def browser_event(user_id: str, url: str, title: str, 
                      duration_seconds: int = None, referrer: str = None) -> NarrativeEvent:
        return NarrativeEvent(
            type=EventType.BROWSER,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "url": url,
                "title": title,
                "duration_seconds": duration_seconds,
                "referrer": referrer,
                "domain": url.split('/')[2] if '://' in url else url
            }
        )

# Convenience function for quick testing
def quick_publish(user_id: str = "default-user", event_type: str = "test"):
    """Quick test function to publish a sample event"""
    publisher = EventPublisher()
    
    builder = EventBuilder()
    if event_type == "photo":
        event = builder.photo_event(user_id, "vacation_photo.jpg", "Beach", "iPhone")
    elif event_type == "song":
        event = builder.song_event(user_id, "Imagine", "John Lennon")
    elif event_type == "email":
        event = builder.email_event(user_id, "Hello World", "friend@example.com")
    else:
        event = NarrativeEvent(
            type=EventType.NOTIFICATION,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"test": "Hello from quick_publish"}
        )
    
    response = publisher.publish_event(event)
    print(f"Published event: {event.event_id}")
    return response

if __name__ == "__main__":
    # Test the publisher
    quick_publish()