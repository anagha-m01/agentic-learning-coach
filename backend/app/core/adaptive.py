"""
Deterministic, Python-side adaptive learning logic.

This module is the single source of truth for:
- score -> topic_decision (next/repeat/revise) mapping
- score -> difficulty_decision (increase/maintain/decrease/revise) mapping
- difficulty-level ladder adjustments
- structured day-type constants (replaces string-matching on topic text)
- near-duplicate question detection
- idempotency fingerprints for safe handling of duplicate client submissions

None of this depends on an LLM: it is pure, deterministic Python so that
progression behavior is reproducible and unit-testable regardless of what
any agent's LLM call returns.
"""
import hashlib
import json
import re
from difflib import SequenceMatcher

# --- Difficulty ladder -------------------------------------------------

LEVELS = ["beginner", "intermediate", "advanced"]

# --- Structured day types (replaces `"practice" in topic.lower()`) -----

DAY_TYPE_LEARNING = "learning"
DAY_TYPE_PRACTICE_TEST = "practice_test"


def day_type_for_index(index: int, total_days: int) -> str:
    """The only place that decides which day is the practice-test day."""
    return DAY_TYPE_PRACTICE_TEST if index == total_days - 1 else DAY_TYPE_LEARNING


def is_practice_day(day_type: str) -> bool:
    return day_type == DAY_TYPE_PRACTICE_TEST


def day_type_of(day: dict) -> str:
    """Structured day_type when present on a plan day; falls back to a
    heuristic only for plans generated before day_type existed."""
    dt = day.get("day_type")
    if dt:
        return dt
    return DAY_TYPE_PRACTICE_TEST if "practice" in str(day.get("topic", "")).lower() else DAY_TYPE_LEARNING


def find_day(plan_data: dict, day_number: int) -> dict:
    """Return the plan entry for day_number, or None."""
    if not plan_data:
        return None
    for day in plan_data.get("plan", []):
        if day.get("day") == day_number:
            return day
    return None


def resolve_day_type(stored_day_type: str, plan_data: dict, day_number: int) -> str:
    """Plan data (if available) is authoritative for a given day; the stored
    snapshot is a fallback so this self-heals if they ever drift."""
    day = find_day(plan_data, day_number)
    if day:
        return day_type_of(day)
    return stored_day_type or DAY_TYPE_LEARNING


# --- Score-based progression (topic and difficulty are separate) -------

def compute_topic_decision(percentage: int) -> str:
    """Topic progression only: next_topic / repeat_topic / revise_topic."""
    if percentage >= 70:
        return "next_topic"
    if percentage >= 50:
        return "repeat_topic"
    return "revise_topic"


def compute_difficulty_decision(percentage: int) -> str:
    """Difficulty progression only: increase / maintain / decrease / revise.

    >=85  -> increase
    70-84 -> maintain
    50-69 -> decrease (repeat with slightly easier/more guided questions)
    <50   -> revise   (revise weak concepts with simpler questions)
    """
    if percentage >= 85:
        return "increase"
    if percentage >= 70:
        return "maintain"
    if percentage >= 50:
        return "decrease"
    return "revise"


def adjust_difficulty(current_level: str, difficulty_decision: str) -> str:
    """Move current_level along LEVELS according to difficulty_decision, clamped."""
    level = current_level if current_level in LEVELS else "beginner"
    idx = LEVELS.index(level)
    if difficulty_decision == "increase":
        idx = min(idx + 1, len(LEVELS) - 1)
    elif difficulty_decision in ("decrease", "revise"):
        idx = max(idx - 1, 0)
    # "maintain" -> unchanged
    return LEVELS[idx]


# --- Duplicate / rephrased question detection ---------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_question_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = _NON_ALNUM.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def is_near_duplicate(candidate_text: str, seen_normalized: list, threshold: float = 0.85) -> bool:
    """Check a raw candidate question string against already-normalized prior question strings."""
    norm = normalize_question_text(candidate_text)
    if not norm:
        return False
    for prior in seen_normalized:
        if norm == prior:
            return True
        if SequenceMatcher(None, norm, prior).ratio() >= threshold:
            return True
    return False


# --- Idempotency fingerprints --------------------------------------------

def fingerprint(value) -> str:
    """Stable short hash of a JSON-serializable value, used to detect duplicate submissions."""
    blob = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    