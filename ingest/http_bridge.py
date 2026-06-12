#!/usr/bin/env python3
# ingest/http_bridge.py
"""
HTTP bridge to accept events from browser extensions, mobile apps, and webhooks.
Runs a simple Flask server that forwards to Kinesis.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingest.event_publisher import EventPublisher, NarrativeEvent, EventType

app = Flask(__name__)
CORS(app)  # Enable CORS for browser extensions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize publisher
publisher = EventPublisher()

@app.route('/_narrative/event', methods=['POST'])
def receive_event():
    """Receive event from browser extension or mobile app"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('type') or not data.get('user_id'):
            return jsonify({'error': 'Missing type or user_id'}), 400
        
        # Convert to NarrativeEvent
        try:
            event_type = EventType(data['type'])
        except ValueError:
            event_type = EventType.NOTIFICATION  # Default fallback
        
        event = NarrativeEvent(
            type=event_type,
            user_id=data['user_id'],
            timestamp=data.get('timestamp', datetime.now().isoformat()),
            data=data.get('data', {})
        )
        
        # Add optional event_id
        if data.get('event_id'):
            event.event_id = data['event_id']
        
        # Publish to Kinesis
        publisher.publish_event(event)
        
        logger.info(f"Received event: {event.event_id} from {event.user_id}")
        return jsonify({'status': 'ok', 'event_id': event.event_id}), 200
        
    except Exception as e:
        logger.error(f"Error processing event: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/_narrative/batch', methods=['POST'])
def receive_batch():
    """Receive batch of events"""
    try:
        events_data = request.json.get('events', [])
        events = []
        
        for event_data in events_data:
            try:
                event_type = EventType(event_data['type'])
                event = NarrativeEvent(
                    type=event_type,
                    user_id=event_data['user_id'],
                    timestamp=event_data.get('timestamp', datetime.now().isoformat()),
                    data=event_data.get('data', {})
                )
                events.append(event)
            except Exception as e:
                logger.warning(f"Skipping invalid event: {e}")
        
        publisher.publish_batch(events)
        logger.info(f"Received batch of {len(events)} events")
        return jsonify({'status': 'ok', 'count': len(events)}), 200
        
    except Exception as e:
        logger.error(f"Error processing batch: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/_narrative/generate', methods=['POST'])
def generate_story():
    """Generate story for a specific date"""
    try:
        data = request.json
        date = data.get('date', datetime.now().strftime("%Y-%m-%d"))
        tone = data.get('tone', 'reflective')
        user_id = data.get('user_id', 'default-user')
        
        # Set tone globally
        os.environ['STORY_TONE'] = tone
        
        # Import Lambda function
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from processor.lambda_function import lambda_handler
        
        # Call Lambda
        result = lambda_handler({
            'action': 'generate_daily_narrative',
            'user_id': user_id,
            'date': date
        }, None)
        
        body = json.loads(result['body'])
        
        # Read the generated story
        story_path = body.get('path')
        if story_path and os.path.exists(story_path):
            with open(story_path, 'r') as f:
                story = f.read()
        else:
            story = "Story generated but file not found"
        
        # Get stats (you'd need to query DynamoDB)
        stats = {
            'total_events': body.get('event_count', 0),
            'photos_taken': 0,
            'emails_received': 0,
            'unique_songs': []
        }
        
        return jsonify({
            'story': story,
            'stats': stats,
            'path': story_path
        }), 200
        
    except Exception as e:
        logger.error(f"Story generation error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/_narrative/stories', methods=['GET'])
def list_stories():
    """List available stories"""
    try:
        stories_dir = 'stories/output'
        stories = []
        
        if os.path.exists(stories_dir):
            for filename in os.listdir(stories_dir):
                if filename.endswith('.md') or filename.endswith('.html'):
                    stories.append({
                        'filename': filename,
                        'date': filename.replace('daily_', '').replace('.md', '').replace('.html', ''),
                        'path': os.path.join(stories_dir, filename)
                    })
        
        return jsonify({'stories': sorted(stories, key=lambda x: x['date'], reverse=True)}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/_narrative/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/_narrative/test', methods=['GET'])
def test():
    """Test endpoint that generates sample events"""
    from ingest.event_publisher import EventBuilder
    
    builder = EventBuilder()
    events = [
        builder.photo_event('test-user', 'test_photo.jpg', 'Home'),
        builder.song_event('test-user', 'Test Song', 'Test Artist'),
        builder.notification_event('test-user', 'Test App', 'Test Notification')
    ]
    
    publisher.publish_batch(events)
    return jsonify({'status': 'ok', 'message': 'Test events sent'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)