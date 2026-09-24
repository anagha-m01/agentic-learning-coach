import json

from app.core.llm_client import call_llm
from app.core.logging_config import get_logger
from app.core.prompt_guards import INJECTION_GUARD, wrap_data
from app.storage.json_store import update_data

logger = get_logger(__name__)

SYSTEM_PROMPT = f"""
You are a Skill Analyzer Agent for an AI learning coach.
Your job is to assess a learner's current level on a topic.

Given the learner's topic, self-reported skill level, and goal,
you must output ONLY a valid JSON object with exactly these fields:
{{
  "topic": "the topic they want to learn",
  "skill_level": "beginner / intermediate / advanced",
  "weaknesses": ["list", "of", "weak", "areas"],
  "starting_topic": "the first subtopic they should study",
  "goal": "their stated goal"
}}

Rules:
- weaknesses must be specific to the topic given
- starting_topic must match the learner's skill level:
  * beginner: foundational introductory concept
  * intermediate: practical core concept
  * advanced: complex advanced concept or one of the identified weak areas
- Output ONLY the JSON. No explanation, no extra text.

{INJECTION_GUARD}
"""


def run_skill_analyzer(session_id: str, topic: str, level: str, goal: str) -> dict:
    user_message = (
        f"{wrap_data('Topic', topic)}\n"
        f"{wrap_data('Self-reported skill level', level)}\n"
        f"{wrap_data('Goal', goal)}"
    )

    response = call_llm(SYSTEM_PROMPT, user_message)

    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("skill_analyzer: malformed LLM JSON, using fallback")
        result = {
            "topic": topic,
            "skill_level": level,
            "weaknesses": [],
            "starting_topic": topic,
            "goal": goal
        }

    # The user's own selected level is always the source of truth for the
    # starting difficulty -- the LLM's assessed "skill_level" is descriptive
    # insight, never allowed to silently override what the learner picked.
    result["skill_level"] = level
    if not isinstance(result.get("weaknesses"), list):
        result["weaknesses"] = []
    if not result.get("topic"):
        result["topic"] = topic
    if not result.get("starting_topic"):
        result["starting_topic"] = topic
    if not result.get("goal"):
        result["goal"] = goal

    update_data(session_id, "skill_analysis", result)
    return result
    