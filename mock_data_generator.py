"""
Mock Data Generator for BIM Standards Chat Analytics
Generates realistic test data with token tracking for dashboard development
"""
import os
import json
import random
from datetime import datetime, timedelta

# Configuration
LOG_DIR = "./mock_data/ChatLogs"
SCREENSHOT_DIR = os.path.join(LOG_DIR, "screenshots")
USERS = ["nrackard", "jdoe", "asmith", "bwayne", "tsmith"]
PROJECTS = ["Project1", "Tower_A", "Stadium_Renovation", "Museum_Wing", "Office_Complex"]
VIEWS = ["L1 - Architectural", "Section 5", "3D Overall", "Detail 12", "L2 - Floor Plan", "Elevation - North"]
BASE_URL = "https://beyerblinderbelle.sharepoint.com/sites/revitstandards/SitePages/"
PAGES = ["Walls.aspx", "Doors.aspx", "LineWeights.aspx", "Exporting.aspx", "Families.aspx", 
         "Worksets.aspx", "ViewTemplates.aspx", "Schedules.aspx"]

SAMPLE_QUERIES = [
    "How do I set up worksets for a new project?",
    "What are the line weight standards?",
    "How should I name door families?",
    "What view templates should I use?",
    "How do I export to PDF correctly?",
    "What's the naming convention for sheets?",
    "How do I fix element warnings?",
    "What workset should walls be on?",
    "How do I create a new schedule?",
    "What are the standard view filters?"
]

def ensure_dirs():
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)

def generate_session():
    user = random.choice(USERS)
    project = random.choice(PROJECTS)
    base_time = datetime.now() - timedelta(days=random.randint(0, 30))
    session_id = base_time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{base_time.strftime('%Y-%m-%d')}_{user}_{session_id}.json"
    
    messages = []
    
    for i in range(random.randint(2, 8)):
        msg_time = base_time + timedelta(seconds=i*45)
        has_screenshot = random.choice([True, False, False])  # 33% chance
        
        # Generate random sources
        num_sources = random.randint(0, 3)
        current_sources = random.sample(PAGES, num_sources) if num_sources > 0 else []
        source_urls = [f"{BASE_URL}{page}" for page in current_sources]
        
        # Select model (weighted to simulate real usage)
        ai_model = random.choices(
            ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-opus-20240229"],
            weights=[70, 25, 5]  # Most queries use Sonnet, some use Haiku, few use Opus
        )[0]
        
        # Generate realistic token counts
        # Input tokens: query + context (standards) + history
        base_input = random.randint(300, 800)  # Query tokens
        context_tokens = num_sources * random.randint(400, 1200)  # Standards context
        history_tokens = i * random.randint(50, 150)  # Conversation history grows
        input_tokens = base_input + context_tokens + history_tokens
        
        # Output tokens: response length
        output_tokens = random.randint(150, 600)
        
        # Duration correlates with token count
        duration = round(2.0 + (output_tokens / 100) + random.uniform(-0.5, 1.0), 2)

        entry = {
            "session_id": session_id,
            "timestamp": msg_time.isoformat(),
            "username": user,
            "model_name": project,
            "view_name": random.choice(VIEWS),
            "query": random.choice(SAMPLE_QUERIES),
            "response": f"Here is the standard for that... (Response {i+1} - {output_tokens} tokens)",
            "source_count": num_sources,
            "source_urls": source_urls,
            "selection_count": random.randint(0, 15),
            "duration_seconds": duration,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "ai_model": ai_model,
            "has_screenshot": has_screenshot,
            "screenshot_path": ""
        }
        
        if has_screenshot:
            img_name = f"{session_id}_{msg_time.strftime('%Y-%m-%dT%H-%M-%S')}.png"
            img_path = os.path.join(SCREENSHOT_DIR, img_name)
            if not os.path.exists(img_path):
                with open(img_path, 'wb') as f:
                    # Create a tiny dummy PNG (1x1 pixel)
                    f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
            entry["screenshot_path"] = img_path
            
        messages.append(entry)

    # Write file (JSONL format)
    with open(os.path.join(LOG_DIR, filename), 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')
            
    print(f"Generated session: {filename} ({len(messages)} messages)")

if __name__ == "__main__":
    ensure_dirs()
    num_sessions = int(input("How many sessions to generate? (default 20): ") or "20")
    
    for _ in range(num_sessions):
        generate_session()
    
    print(f"\n✓ Generated {num_sessions} sessions in {LOG_DIR}")
    print(f"✓ Run your backend server and point it to: {os.path.abspath(LOG_DIR)}")
