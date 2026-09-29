import json
import urllib.request
from .models import ParentNotificationConfig

def send_notification(title, message, event_type="general"):
    # Find all parents who have a webhook configured
    configs = ParentNotificationConfig.objects.exclude(webhook_url__isnull=True).exclude(webhook_url="")
    
    for config in configs:
        # Check preferences based on event type
        if event_type == "chore_waiting" and not config.notify_chore_waiting:
            continue
        if event_type == "reward_requested" and not config.notify_reward_requested:
            continue
        if event_type == "quiz_completed" and not config.notify_quiz_completed:
            continue
            
        payload = {
            "event": event_type,
            "title": title,
            "message": message,
        }
        
        req = urllib.request.Request(
            config.webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                pass
        except Exception as e:
            print(f"Failed to send webhook for {config.parent.name}: {e}")