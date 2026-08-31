import json
import os
import tempfile
import threading

DATA_FILE = "data/learner_data.json"
_lock = threading.Lock()  # prevent concurrent writes

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, OSError):
        save_data({})
        return {}

def save_data(data: dict):
    os.makedirs("data", exist_ok=True)
    with _lock:
        # Windows-safe write — delete first, then write
        tmp_path = DATA_FILE + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)      # 👈 delete original first (Windows fix)
        os.rename(tmp_path, DATA_FILE)

def update_data(key: str, value):
    with _lock:
        data = load_data()
        data[key] = value
        # Write directly without calling save_data to avoid double lock
        os.makedirs("data", exist_ok=True)
        tmp_path = DATA_FILE + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        os.rename(tmp_path, DATA_FILE)

def get_value(key: str, default=None):
    data = load_data()
    return data.get(key, default)