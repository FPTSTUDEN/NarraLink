#!/usr/bin/env python3
# scripts/send_test_events.py
"""
Send a variety of test events to verify ingestion pipeline.
"""

import sys
import os
import time
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingest.event_publisher import EventPublisher, EventBuilder

def send_test_events():
    publisher = EventPublisher()
    builder = EventBuilder()
    
    # user_id = "test-user-" + datetime.now().strftime("%Y%m%d")
    user_id = "test-user"  # Replace with actual user ID for testing
    
    print(f"Sending test events for user: {user_id}\n")
    
    # Photo events
    for i in range(3):
        event = builder.photo_event(
            user_id,
            f"vacation_photo_{i}.jpg",
            random.choice(["Beach", "Mountains", "City", "Home"]),
            random.choice(["iPhone", "DSLR", "Screenshot"])
        )
        publisher.publish_event(event)
        print(f"✓ Photo {i+1}: {event.data['filename']}")
        time.sleep(0.5)
    
    # Song events
    songs = [
        ("Bohemian Rhapsody", "Queen"),
        ("Imagine", "John Lennon"),
        ("Billie Jean", "Michael Jackson"),
        ("Like a Rolling Stone", "Bob Dylan")
    ]
    for title, artist in songs[:2]:
        event = builder.song_event(user_id, title, artist, platform="Spotify")
        publisher.publish_event(event)
        print(f"✓ Song: {title} by {artist}")
        time.sleep(0.5)
    
    # Email events
    emails = [
        ("Weekend Plans", "friend@example.com", "high"),
        ("Newsletter", "news@example.com", "low"),
        ("Work Update", "boss@company.com", "high")
    ]
    for subject, from_addr, importance in emails[:2]:
        event = builder.email_event(user_id, subject, from_addr, importance)
        publisher.publish_event(event)
        print(f"✓ Email: {subject}")
        time.sleep(0.5)
    
    # Browser events
    urls = [
        ("https://github.com", "GitHub"),
        ("https://news.ycombinator.com", "Hacker News"),
        ("https://reddit.com", "Reddit")
    ]
    for url, title in urls:
        event = builder.browser_event(user_id, url, title, duration_seconds=random.randint(30, 300))
        publisher.publish_event(event)
        print(f"✓ Browser: {title}")
        time.sleep(0.5)
    
    # Calendar events
    now = datetime.now()
    event = builder.calendar_event(
        user_id,
        "Team Meeting",
        (now + timedelta(hours=2)).isoformat(),
        (now + timedelta(hours=3)).isoformat(),
        "Zoom",
        ["alice@example.com", "bob@example.com"]
    )
    publisher.publish_event(event)
    print(f"✓ Calendar: Team Meeting")
    
    print(f"\n✅ Sent {9} test events to Kinesis")
    print("Check Lambda logs to see processing")

if __name__ == "__main__":
    send_test_events()