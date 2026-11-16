import json
import time
import uuid
from pathlib import Path

DATA_DIR = Path.home() / ".local/share/mistral-bar"
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"


def new_conversation(mode="chat"):
    return {
        "id": uuid.uuid4().hex,
        "title": "New chat",
        "mode": mode,
        "created": time.time(),
        "messages": [],
    }


def load_conversations():
    if CONVERSATIONS_FILE.exists():
        try:
            with open(CONVERSATIONS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_conversations(conversations):
    CONVERSATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(conversations, f, indent=2)
