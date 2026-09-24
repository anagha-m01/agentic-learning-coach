import json
from app.core.adaptive import day_type_for_index, DAY_TYPE_PRACTICE_TEST
from app.core.llm_client import call_llm
from app.core.logging_config import get_logger
from app.core.prompt_guards import INJECTION_GUARD, wrap_data
from app.storage.json_store import update_data, get_value

logger = get_logger(__name__)

LEVEL_PACING_HINT = {
    "beginner": (
        "The learner is a BEGINNER. Day 1 must be the absolute basics: "
        "core vocabulary and the simplest possible foundational ideas, "
        "assuming zero prior exposure. Progress gradually from basics to intermediate topics. "
        "Do NOT place advanced or specialized subtopics in early days."
    ),
    "intermediate": (
        "The learner is INTERMEDIATE. Day 1 should start from practical core mechanics "
        "and intermediate concepts. Skip elementary vocabulary/definitions. "
        "Build steadily toward advanced topics."
    ),
    "advanced": (
        "The learner is ADVANCED. Skip all introductory 101 material, basic definitions, and elementary "
        "concepts entirely. Day 1 must start directly with advanced concepts, in-depth mechanics, "
        "architectures, or optimization. Build the plan specifically around the learner's identified "
        "weak areas and focus areas."
    ),
}


def build_prompt(days: int, level: str) -> str:
    learning_days = days - 1
    level_hint = LEVEL_PACING_HINT.get(level, LEVEL_PACING_HINT["beginner"])

    if level == "advanced":
        progression_rules = (
            "DIFFICULTY PROGRESSION (ADVANCED LEARNER):\n"
            "- Day 1: Start directly with complex, advanced concepts or the learner's identified focus areas. "
            "DO NOT start with 101 definitions or introductory basics.\n"
            "- Subsequent Days: Deepen into advanced architectures, edge cases, trade-offs, and optimization.\n"
            "- Tailor the plan directly to the learner's identified weaknesses and focus areas.\n"
        )
        strict_level_rule = "- For an advanced learner: Day 1 MUST be advanced material, NOT 101 fundamentals"
    elif level == "intermediate":
        progression_rules = (
            "DIFFICULTY PROGRESSION (INTERMEDIATE LEARNER):\n"
            "- Day 1: Core operational concepts and intermediate mechanics (skip basic definitions).\n"
            "- Subsequent Days: Advance steadily toward complex scenarios and advanced topics.\n"
        )
        strict_level_rule = "- For an intermediate learner: skip elementary definitions on Day 1"
    else:
        progression_rules = (
            "DIFFICULTY PROGRESSION (BEGINNER LEARNER):\n"
            "- Day 1: Absolute basics and core vocabulary only.\n"
            "- Day 2+: Gradually increase complexity, building on all previous days.\n"
            "- NEVER place advanced or specialized subtopics in early days for a beginner.\n\n"
            "For beginners on \"Machine Learning\", progress from:\n"
            "  Fundamentals → Supervised Learning → Unsupervised Learning → Model Evaluation\n"
            "For beginners on \"Python\":\n"
            "  Variables/Data Types → Conditionals → Loops → Functions → OOP\n"
        )
        strict_level_rule = f"- For a beginner: no advanced or niche subtopics before Day {max(3, learning_days // 2 + 1)}"

    return f"""
You are a Learning Planner Agent for an AI learning coach.
Create a structured study plan for EXACTLY {days} days.

The plan has {learning_days} learning days + 1 final practice test day (Day {days}).

{level_hint}

TOPIC DISTRIBUTION RULES based on number of learning days ({learning_days} days):
- Each day can cover ONE or MULTIPLE subtopics depending on how many days are available
- Fewer days = more subtopics bundled per day
- More days = one focused subtopic per day with more depth

{progression_rules}
For any topic: progress naturally from the learner's starting point.
If days are few, BUNDLE multiple subtopics together per day.
If days are many, give each subtopic its own day with more depth.

You must output ONLY a valid JSON object like this:
{{
  "plan": [
    {{
      "day": 1,
      "topic": "Day 1 Topic",
      "description": "Description of Day 1 topics and goals"
    }},
    {{
      "day": 2,
      "topic": "Day 2 Topic",
      "description": "Description of Day 2 topics and goals"
    }},
    {{
      "day": {days},
      "topic": "Practice Test",
      "description": "Revise all topics from all previous days"
    }}
  ],
  "total_days": {days},
  "summary": "one line summary of the plan"
}}

STRICT Rules:
- Plan array MUST have EXACTLY {days} items — count before responding
{strict_level_rule}
- Bundle subtopics naturally when days are few
- Day {days} = ALWAYS "Practice Test"
- Output ONLY the JSON. No extra text.

{INJECTION_GUARD}
"""


def run_planner(session_id: str, days: int = 5) -> dict:
    if days < 2:
        days = 5  # Enforce minimum days

    skill_data = get_value(session_id, "skill_analysis")
    if not skill_data:
        return None

    topic = skill_data.get("topic", "the topic")
    # The learner's own selected level (preserved verbatim by skill_analyzer)
    # is the source of truth for pacing, not any inferred value.
    level = get_value(session_id, "difficulty") or skill_data.get("skill_level", "beginner")

    weaknesses = skill_data.get("weaknesses", [])
    weaknesses_part = (
        f"{wrap_data('Target focus areas / weaknesses', ', '.join(weaknesses))}\n"
        if weaknesses else ""
    )

    system_prompt = build_prompt(days, level)
    user_message = (
        f"{wrap_data('Learner skill analysis', json.dumps(skill_data, indent=2))}\n\n"
        f"{wrap_data('Topic', topic)}\n"
        f"{wrap_data('Skill level', level)}\n"
        f"{weaknesses_part}"
        f"Total days: {days} (including practice test on Day {days})\n"
        f"Learning days available: {days - 1}\n\n"
        f"IMPORTANT RULES:\n"
        f"1. Generate EXACTLY {days} days — not more, not less\n"
        f"2. Day 1 must match the level guidance in the system prompt\n"
        f"3. Progress naturally from the learner's level (for advanced learners, dive straight into advanced material)\n"
        f"4. Bundle multiple subtopics per day if days are few\n"
        f"5. Day {days} must be Practice Test"
    )

    response = call_llm(system_prompt, user_message)

    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        result  = json.loads(cleaned)
    except json.JSONDecodeError:
        result  = {"plan": [], "total_days": days, "summary": ""}

    plan = result.get("plan", [])

    # Retry if plan length mismatches days
    if len(plan) != days:
        logger.warning(f"planner: got {len(plan)} days, expected {days}, retrying")
        response2 = call_llm(system_prompt,
            f"Previous attempt gave wrong number of days.\n"
            f"YOU MUST RETURN EXACTLY {days} DAYS.\n"
            f"{wrap_data('Topic', topic)}\n"
            f"{wrap_data('Skill level', level)}\n"
            f"Count every item in the plan array — it must equal {days}."
        )
        try:
            result = json.loads(response2.strip().strip("```json").strip("```").strip())
            plan   = result.get("plan", [])
        except json.JSONDecodeError:
            pass

    # Trim excess days
    if len(plan) > days:
        plan = plan[:days]

    # Pad missing days
    while len(plan) < days:
        plan.append({
            "day": len(plan) + 1,
            "topic": f"{topic} — Continued Practice",
            "description": "Continue practising concepts from previous days"
        })

    # Renumber days sequentially and assign a structured day_type
    # deterministically -- never inferred from the topic string, so it
    # cannot break if the LLM phrases the last day differently or in
    # another language.
    for i, day in enumerate(plan):
        day["day"] = i + 1
        day["day_type"] = day_type_for_index(i, len(plan))

    # The final day is always, deterministically, the practice test --
    # enforced structurally rather than by checking for words like
    # "practice"/"test"/"revision" in the LLM's chosen title.
    plan[-1]["topic"] = "Practice Test"
    plan[-1]["description"] = "Revise all topics and take a full practice test"
    plan[-1]["day_type"] = DAY_TYPE_PRACTICE_TEST

    result["plan"]       = plan
    result["total_days"] = len(plan)

    update_data(session_id, "total_days", len(plan))
    update_data(session_id, "study_plan", result)
    return result
    