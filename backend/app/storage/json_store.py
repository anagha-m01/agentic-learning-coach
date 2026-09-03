"""Session-scoped JSON file storage with opportunistic expiration pruning."""
import json
import os
import threading
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.logging_config import get_logger, mask_session

logger = get_logger(__name__)

DATA_FILE = os.path.join(settings.data_dir, "learner_data.json")
_lock = threading.Lock()


def _read_raw() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Corrupt session store, resetting", extra={
            "extra_fields": {"error": str(e)}
        })
        return {}


def _write_raw(all_data: dict) -> None:
    os.makedirs(settings.data_dir, exist_ok=True)
    tmp_path = DATA_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(all_data, f, indent=2)
    os.replace(tmp_path, DATA_FILE)  # Atomic file replacement


def _prune_expired(all_data: dict) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.session_ttl_hours)
    kept = {}
    for sid, payload in all_data.items():
        last_seen_raw = payload.get("_last_seen") if isinstance(payload, dict) else None
        try:
            last_seen = datetime.fromisoformat(last_seen_raw) if last_seen_raw else None
        except ValueError:
            last_seen = None
        if last_seen is None or last_seen >= cutoff:
            kept[sid] = payload
    return kept


def load_session(session_id: str) -> dict:
    with _lock:
        all_data = _read_raw()
        return dict(all_data.get(session_id, {}))


def get_value(session_id: str, key: str, default=None):
    return load_session(session_id).get(key, default)


def update_data(session_id: str, key: str, value) -> None:
    with _lock:
        all_data = _read_raw()
        all_data = _prune_expired(all_data)
        session_data = all_data.get(session_id, {})
        session_data[key] = value
        session_data["_last_seen"] = datetime.now(timezone.utc).isoformat()
        all_data[session_id] = session_data
        _write_raw(all_data)
    logger.debug("session updated", extra={
        "extra_fields": {"session": mask_session(session_id), "key": key}
    })


def save_session(session_id: str, data: dict) -> None:
    """Replace or clear session data dictionary."""
    with _lock:
        all_data = _read_raw()
        all_data = _prune_expired(all_data)
        if data:
            data["_last_seen"] = datetime.now(timezone.utc).isoformat()
            all_data[session_id] = data
        else:
            all_data.pop(session_id, None)
        _write_raw(all_data)
        