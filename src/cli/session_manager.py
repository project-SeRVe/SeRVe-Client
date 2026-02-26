import os
import json
from pathlib import Path

SESSION_DIR = Path.home() / ".serve"
SESSION_FILE = SESSION_DIR / "session.json"

def get_session():
    if not SESSION_FILE.exists():
        return None
    try:
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None

def save_session(access_token, user_id, email, encrypted_private_key):
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_data = {
        "access_token": access_token,
        "user_id": user_id,
        "email": email,
        "encrypted_private_key": encrypted_private_key
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(session_data, f)
        
def clear_session():
    if SESSION_FILE.exists():
        os.remove(SESSION_FILE)
