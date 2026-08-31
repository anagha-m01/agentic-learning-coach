import json
from app.core.llm_client import call_llm
from app.storage.json_store import update_data

SYSTEM_PROMPT = """
You are a Skill Analyzer Agent for an AI learning coach.
Your job is to assess a learner's current level on a topic.

Given the learner's topic, self-reported skill level, and goal,
you must output ONLY a valid JSON object with exactly these fields:
{
  "topic": "the topic they want to learn",
  "skill_level": "beginner / intermediate / advanced",
  "weaknesses": ["list", "of", "weak", "areas"],
  "starting_topic": "the first subtopic they should study",
  "goal": "their stated goal"
}

Rules:
- weaknesses must be specific to the topic given
- starting_topic must be the most fundamental concept of the topic
- Output ONLY the JSON. No explanation, no extra text.
"""

def run_skill_analyzer(topic: str, level: str, goal: str) -> dict:
    user_message = f"Topic: {topic}\nSkill level: {level}\nGoal: {goal}"

    response = call_llm(SYSTEM_PROMPT, user_message)

    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        result = {
            "topic": topic,
            "skill_level": level,
            "weaknesses": [],
            "starting_topic": topic,
            "goal": goal
        }

    update_data("skill_analysis", result)
    return result