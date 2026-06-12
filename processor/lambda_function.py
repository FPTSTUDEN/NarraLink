#!/usr/bin/env python3
"""
Lambda function for generating narratives from daily events.
Supports both mock AI mode (for testing) and real LLM integration.
"""

import json
import os
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict
import random
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TABLE_NAME = os.getenv('TABLE_NAME', 'narrative-state')
BUCKET_NAME = os.getenv('BUCKET_NAME', 'narrative-store')
STREAM_NAME = os.getenv('STREAM_NAME', 'user-events')
USE_MOCK_AI = os.getenv('USE_MOCK_AI', 'true').lower() == 'true'
STORY_TONE = os.getenv('STORY_TONE', 'reflective')
OUTPUT_FORMAT = os.getenv('OUTPUT_FORMAT', 'markdown')

# Initialize AWS clients (will use emulator endpoints if configured)
endpoint_url = os.getenv('AWS_ENDPOINT_URL')
if endpoint_url:
    dynamodb = boto3.resource('dynamodb', endpoint_url=endpoint_url)
    s3 = boto3.client('s3', endpoint_url=endpoint_url)
    lambda_client = boto3.client('lambda', endpoint_url=endpoint_url)
else:
    dynamodb = boto3.resource('dynamodb')
    s3 = boto3.client('s3')
    lambda_client = boto3.client('lambda')

# Get table reference
table = dynamodb.Table(TABLE_NAME)

class NarrativeGenerator:
    """Generates stories from event streams"""
    
    def __init__(self, user_id: str = "default-user", mock_mode: bool = USE_MOCK_AI):
        self.user_id = user_id
        self.mock_mode = mock_mode
        self.events = []
        self.daily_context = {}
        
    def load_daily_events(self, date: str = None) -> List[Dict]:
        """Load events for a specific date from DynamoDB"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Query events for this user and date
        response = table.query(
            KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
            ExpressionAttributeValues={
                ":pk": f"user::{self.user_id}",
                ":sk": f"event::{date}"
            }
        )
        
        events = []
        for item in response.get('Items', []):
            events.append({
                'timestamp': item['sk'].replace('event::', ''),
                'type': item.get('event_type'),
                'data': json.loads(item.get('event_data', '{}'))
            })
        
        self.events = sorted(events, key=lambda x: x['timestamp'])
        return self.events
    
    def group_events_by_time(self) -> Dict[str, List]:
        """Group events into morning, afternoon, evening"""
        groups = {
            'morning': [],    # 6AM - 12PM
            'afternoon': [],  # 12PM - 5PM
            'evening': []     # 5PM - 12AM
        }
        
        for event in self.events:
            try:
                dt = datetime.fromisoformat(event['timestamp'])
                hour = dt.hour
                
                if 6 <= hour < 12:
                    groups['morning'].append(event)
                elif 12 <= hour < 17:
                    groups['afternoon'].append(event)
                else:
                    groups['evening'].append(event)
            except:
                groups['evening'].append(event)  # Default fallback
                
        return groups
    
    def extract_statistics(self) -> Dict:
        """Extract statistics from events"""
        stats = {
            'total_events': len(self.events),
            'event_counts': defaultdict(int),
            'unique_songs': set(),
            'photos_taken': 0,
            'emails_received': 0,
            'browser_visits': 0,
            'notifications': 0,
            'top_domains': defaultdict(int)
        }
        
        for event in self.events:
            event_type = event['type']
            stats['event_counts'][event_type] += 1
            
            if event_type == 'photo':
                stats['photos_taken'] += 1
            elif event_type == 'email':
                stats['emails_received'] += 1
            elif event_type == 'song':
                if 'title' in event['data']:
                    stats['unique_songs'].add(f"{event['data'].get('title')} by {event['data'].get('artist', 'Unknown')}")
            elif event_type == 'browser':
                stats['browser_visits'] += 1
                domain = event['data'].get('domain', 'unknown')
                stats['top_domains'][domain] += 1
            elif event_type == 'notification':
                stats['notifications'] += 1
                
        stats['unique_songs'] = list(stats['unique_songs'])
        stats['top_domains'] = dict(sorted(stats['top_domains'].items(), key=lambda x: x[1], reverse=True)[:3])
        
        return stats
    
    def generate_mock_story(self, stats: Dict, grouped_events: Dict) -> str:
        """Generate a story using mock AI (template-based)"""
        
        # Choose story template based on tone
        if STORY_TONE == 'humorous':
            return self._generate_humorous_story(stats, grouped_events)
        elif STORY_TONE == 'poetic':
            return self._generate_poetic_story(stats, grouped_events)
        elif STORY_TONE == 'dramatic':
            return self._generate_dramatic_story(stats, grouped_events)
        else:  # reflective
            return self._generate_reflective_story(stats, grouped_events)
    
    def _generate_reflective_story(self, stats: Dict, grouped_events: Dict) -> str:
        """Generate reflective journal-style narrative"""
        
        date_str = datetime.now().strftime("%B %d, %Y")
        
        story = f"# {date_str}\n\n"
        
        # Morning section
        morning_events = grouped_events['morning']
        if morning_events:
            story += "## Morning\n\n"
            for event in morning_events[:3]:  # Limit to top 3
                story += self._format_event_reflective(event) + "\n\n"
        
        # Afternoon section
        afternoon_events = grouped_events['afternoon']
        if afternoon_events:
            story += "## Afternoon\n\n"
            for event in afternoon_events[:3]:
                story += self._format_event_reflective(event) + "\n\n"
        
        # Evening section
        evening_events = grouped_events['evening']
        if evening_events:
            story += "## Evening\n\n"
            for event in evening_events[:3]:
                story += self._format_event_reflective(event) + "\n\n"
        
        # Summary
        story += "## Today's Summary\n\n"
        story += f"Today was marked by {stats['total_events']} digital moments. "
        
        if stats['photos_taken'] > 0:
            story += f"You captured {stats['photos_taken']} photograph{'s' if stats['photos_taken'] > 1 else ''}, "
        
        if stats['emails_received'] > 0:
            story += f"received {stats['emails_received']} email{'s' if stats['emails_received'] > 1 else ''}, "
        
        if stats['unique_songs']:
            songs_text = ', '.join(stats['unique_songs'][:2])
            story += f"and let the music of {songs_text} shape your emotions. "
        
        if stats['browser_visits'] > 0:
            story += f"\n\nYour curiosity led you to {stats['browser_visits']} websites, "
            if stats['top_domains']:
                top_domain = list(stats['top_domains'].keys())[0]
                story += f"with {top_domain} capturing most of your attention. "
        
        story += "\n\n*Reflection: What will tomorrow bring?*"
        
        return story
    
    def _generate_humorous_story(self, stats: Dict, grouped_events: Dict) -> str:
        """Generate funny, lighthearted story"""
        
        templates = [
            "Today was a rollercoaster of {event_count} digital events. Let's recap the highlights (and lowlights):",
            "Your digital self had quite the adventure today. Here's what happened:",
            "Plot twist: You were more productive than you think. Here's proof:"
        ]
        
        story = f"# {datetime.now().strftime('%B %d, %Y')}\n\n"
        story += random.choice(templates).format(event_count=stats['total_events'])
        story += "\n\n"
        
        # Funny observations
        if stats['notifications'] > 10:
            story += "🔔 **Notification overload!** Your phone buzzed so much it's now considering a career as a massage device.\n\n"
        elif stats['notifications'] > 5:
            story += "📱 *Bzzt bzzt* — that's the sound of your phone demanding attention (again).\n\n"
        
        if stats['photos_taken'] == 0:
            story += "📸 **Zero photos today.** Either you were living in the moment or your camera is feeling neglected.\n\n"
        elif stats['photos_taken'] > 5:
            story += f"📸 You took {stats['photos_taken']} photos. At this rate, your phone storage is filing for divorce.\n\n"
        
        if stats['unique_songs']:
            song = stats['unique_songs'][0]
            story += f"🎵 Your soundtrack today: *{song}*. Perfect for pretending you're in a movie montage.\n\n"
        
        if stats['browser_visits'] > 20:
            story += f"💻 You visited {stats['browser_visits']} websites. That's not browsing, that's a digital marathon. Hydrate!\n\n"
        
        story += "\n**The verdict:** Your digital self is thriving, even if your real self needs coffee. ☕"
        
        return story
    
    def _generate_poetic_story(self, stats: Dict, grouped_events: Dict) -> str:
        """Generate poetic, lyrical narrative"""
        
        story = f"# {datetime.now().strftime('%B %d, %Y')}\n\n"
        story += "> *A digital diary in verse*\n\n"
        
        # Poetic lines
        poems = []
        
        if stats['photos_taken'] > 0:
            poems.append(f"Through lens I captured light and shade,\nA moment's grace, a memory made.")
        
        if stats['unique_songs']:
            songs_text = ', '.join(stats['unique_songs'][:1])
            poems.append(f"Melodies of {songs_text} filled the air,\nA symphony of ones and zeroes, beyond compare.")
        
        if stats['emails_received'] > 0:
            poems.append(f"Words in inbox, a digital dove,\nMessages of connection, and ones of love.")
        
        if stats['browser_visits'] > 0:
            poems.append(f"Through hyperlinks my cursor flew,\nDiscovering worlds both old and new.")
        
        if stats['notifications'] > 0:
            poems.append(f"Chimes and buzzes, a digital beat,\nThe rhythm of a life both bitter and sweet.")
        
        story += '\n\n'.join(poems)
        
        story += "\n\n---\n\n"
        story += f"*{stats['total_events']} moments composed*\n"
        story += f"*Into {len([e for e in stats['event_counts'].values() if e > 0])} different scenes*\n"
        story += "*A life in data, beautifully exposed*\n"
        story += "*In the spaces between.*"
        
        return story
    
    def _generate_dramatic_story(self, stats: Dict, grouped_events: Dict) -> str:
        """Generate dramatic, story-like narrative"""
        
        story = f"# The Chronicle of {datetime.now().strftime('%B %d')}\n\n"
        
        opening_lines = [
            f"The day began like any other, with {stats['total_events']} digital whispers waiting to be heard...",
            f"In the great theater of your life, today's performance featured {stats['total_events']} acts...",
            f"The algorithm knew something you didn't: today would be different."
        ]
        
        story += random.choice(opening_lines) + "\n\n"
        
        # Dramatic event sequences
        all_events = grouped_events['morning'] + grouped_events['afternoon'] + grouped_events['evening']
        
        if all_events:
            # Find most notable event
            notable_event = max(all_events, key=lambda x: len(str(x)))
            story += self._format_event_dramatic(notable_event) + "\n\n"
            
            # Build tension
            if stats['notifications'] > 3:
                story += f"*{stats['notifications']} notifications pierced the silence, each one a potential plot twist.*\n\n"
            
            if stats['unique_songs']:
                song = stats['unique_songs'][0]
                story += f"*The soundtrack swelled — {song} — as if the universe was scoring your every move.*\n\n"
            
            # Climax (most intense moment)
            if stats['emails_received'] > 0:
                story += "*Then, the email arrived. The one that would change everything...* (Or at least require a reply by tomorrow.)\n\n"
        
        story += "\n**To be continued...**"
        
        return story
    
    def _format_event_reflective(self, event: Dict) -> str:
        """Format event for reflective narrative"""
        
        event_type = event['type']
        data = event['data']
        time = datetime.fromisoformat(event['timestamp']).strftime("%-I:%M %p")
        
        if event_type == 'photo':
            return f"- **{time}**: Captured a photo of *{data.get('location', 'a moment')}*"
        elif event_type == 'song':
            return f"- **{time}**: Listened to *{data.get('title', 'music')}* by {data.get('artist', 'an artist')}"
        elif event_type == 'email':
            return f"- **{time}**: Received email: *{data.get('subject', 'No subject')}*"
        elif event_type == 'calendar':
            return f"- **{time}**: Calendar reminder: {data.get('title', 'Event')}"
        elif event_type == 'notification':
            return f"- **{time}**: Notification from {data.get('app', 'app')}: {data.get('title', 'Alert')}"
        elif event_type == 'browser':
            return f"- **{time}**: Visited *{data.get('domain', 'website')}*"
        else:
            return f"- **{time}**: {event_type} event recorded"
    
    def _format_event_dramatic(self, event: Dict) -> str:
        """Format event for dramatic narrative"""
        
        event_type = event['type']
        data = event['data']
        time = datetime.fromisoformat(event['timestamp']).strftime("%-I:%M %p")
        
        dramatic_templates = {
            'photo': f"At {time}, you paused. The world demanded to be captured. You raised your camera and *click* — another memory saved from oblivion.",
            'song': f"The clock struck {time} and suddenly, music. {data.get('title', 'Melody')} filled the room like an old friend.",
            'email': f"{time} — the inbox chimed. A message waited, unread, full of potential.",
            'calendar': f"*{time}*: The calendar blinked. An appointment. A commitment. A promise to your future self.",
            'notification': f"*BZZT* — {time}. Your device demanded attention. {data.get('title', 'Something')} needed you."
        }
        
        return dramatic_templates.get(event_type, f"At {time}, something happened. Something worth remembering.")
    
    def generate_real_story(self, stats: Dict, grouped_events: Dict) -> str:
        """Generate story using real LLM (Ollama or Bedrock)"""
        
        # Prepare prompt
        prompt = self._build_llm_prompt(stats, grouped_events)
        
        try:
            # Try Ollama first (local)
            import requests
            ollama_endpoint = os.getenv('OLLAMA_ENDPOINT', 'http://localhost:11434')
            model = os.getenv('OLLAMA_MODEL', 'llama2')
            
            response = requests.post(
                f"{ollama_endpoint}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', self.generate_mock_story(stats, grouped_events))
            else:
                logger.warning(f"Ollama returned {response.status_code}, falling back to mock")
                return self.generate_mock_story(stats, grouped_events)
                
        except Exception as e:
            logger.warning(f"LLM generation failed: {e}, using mock mode")
            return self.generate_mock_story(stats, grouped_events)
    
    def _build_llm_prompt(self, stats: Dict, grouped_events: Dict) -> str:
        """Build prompt for LLM"""
        
        date_str = datetime.now().strftime("%B %d, %Y")
        
        # Sample events for context
        sample_events = []
        for time_group, events in grouped_events.items():
            for event in events[:2]:  # Top 2 per time period
                sample_events.append(f"- {event['type']}: {json.dumps(event['data'])[:100]}")
        
        events_text = '\n'.join(sample_events)
        
        prompt = f"""You are a personal narrative generator. Based on the following digital events from {date_str}, create a {STORY_TONE} journal entry.

Statistics:
- Total events: {stats['total_events']}
- Photos taken: {stats['photos_taken']}
- Emails received: {stats['emails_received']}
- Unique songs: {', '.join(stats['unique_songs'][:3])}
- Top websites: {', '.join(stats['top_domains'].keys())}

Sample events:
{events_text}

Write a {STORY_TONE} narrative (200-300 words) that weaves these moments into a coherent story. Format as markdown with a title.
"""
        
        return prompt
    
    def save_story(self, story: str, date: str = None) -> str:
        """Save generated story to S3 and local file"""
        
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Determine file extension
        ext = 'md' if OUTPUT_FORMAT == 'markdown' else 'html'
        filename = f"daily_{date}.{ext}"
        
        # Convert to HTML if needed
        if OUTPUT_FORMAT == 'html':
            import markdown
            story = markdown.markdown(story)
        
        # Save to S3
        key = f"stories/user={self.user_id}/year={date[:4]}/month={date[5:7]}/{filename}"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=story.encode('utf-8'),
            ContentType='text/markdown' if OUTPUT_FORMAT == 'markdown' else 'text/html'
        )
        
        # Also save locally for easy access
        local_path = f"stories/output/{filename}"
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w') as f:
            f.write(story)
        
        logger.info(f"Story saved to s3://{BUCKET_NAME}/{key} and {local_path}")
        
        # Save metadata to DynamoDB
        table.put_item(
            Item={
                'pk': f"user::{self.user_id}",
                'sk': f"story::{date}",
                'story_path': key,
                'generated_at': datetime.now().isoformat(),
                'event_count': len(self.events),
                'tone': STORY_TONE
            }
        )
        
        return local_path

def lambda_handler(event, context):
    """Main Lambda entry point"""
    
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Determine action
    action = event.get('action', 'process_events')
    user_id = event.get('user_id', os.getenv('NARRATIVE_USER_ID', 'default-user'))
    
    generator = NarrativeGenerator(user_id=user_id, mock_mode=USE_MOCK_AI)
    
    if action == 'generate_daily_narrative':
        # Generate story for today
        date = event.get('date', datetime.now().strftime("%Y-%m-%d"))
        
        # Load events
        events = generator.load_daily_events(date)
        
        if not events:
            logger.info(f"No events found for {date}")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'No events for {date}'})
            }
        
        # Group and analyze
        grouped = generator.group_events_by_time()
        stats = generator.extract_statistics()
        
        # Generate story
        if USE_MOCK_AI:
            story = generator.generate_mock_story(stats, grouped)
        else:
            story = generator.generate_real_story(stats, grouped)
        
        # Save story
        path = generator.save_story(story, date)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Story generated for {date}',
                'path': path,
                'event_count': len(events),
                'mock_mode': USE_MOCK_AI
            })
        }
    
    elif action == 'process_batch':
        # Process events from Kinesis (real-time)
        for record in event.get('Records', []):
            try:
                kinesis_data = json.loads(record['kinesis']['data'])
                logger.info(f"Processing event: {kinesis_data.get('type')}")
                
                # Store raw event in S3
                user_id = kinesis_data.get('user_id', 'unknown')
                timestamp = kinesis_data.get('timestamp', datetime.now().isoformat())
                date = timestamp[:10]
                
                s3_key = f"raw/user={user_id}/year={date[:4]}/month={date[5:7]}/day={date[8:10]}/{kinesis_data.get('event_id', timestamp)}.json"
                s3.put_object(
                    Bucket=BUCKET_NAME,
                    Key=s3_key,
                    Body=json.dumps(kinesis_data)
                )
                
                # Store in DynamoDB for querying
                table.put_item(
                    Item={
                        'pk': f"user::{user_id}",
                        'sk': f"event::{timestamp}",
                        'gsi1pk': f"day::{date}",
                        'gsi1sk': timestamp,
                        'event_type': kinesis_data.get('type'),
                        'event_data': json.dumps(kinesis_data.get('data', {}))
                    }
                )
                
            except Exception as e:
                logger.error(f"Error processing record: {e}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Processed {len(event.get("Records", []))} events'})
        }
    
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Unknown action: {action}'})
        }

# Local testing
if __name__ == "__main__":
    # Test with mock mode
    test_event = {
        'action': 'generate_daily_narrative',
        'user_id': 'test-user'
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))