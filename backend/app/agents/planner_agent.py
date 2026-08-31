import json
from app.core.llm_client import call_llm
from app.storage.json_store import update_data, get_value

def build_prompt(days: int) -> str:
    learning_days = days - 1

    return f"""
You are a Learning Planner Agent for an AI learning coach.
Create a structured study plan for EXACTLY {days} days.

The plan has {learning_days} learning days + 1 final practice test day (Day {days}).

TOPIC DISTRIBUTION RULES based on number of learning days ({learning_days} days):
- Each day can cover ONE or MULTIPLE subtopics depending on how many days are available
- Fewer days = more subtopics bundled per day
- More days = one focused subtopic per day with more depth
- NEVER skip foundational topics to jump to advanced ones

DIFFICULTY PROGRESSION — this is STRICT:
- Day 1: ALWAYS the most basic, beginner-friendly fundamentals only
- Day 2: Slightly harder than Day 1, still foundational
- Day 3+: Gradually increase complexity, building on ALL previous days
- NEVER place advanced or specialised subtopics in early days

For "Machine Learning" specifically, the correct order is:
  Fundamentals → Supervised Learning → Unsupervised Learning → Model Evaluation → Advanced topics
  NOT: jumping to Deep Learning or Model Interpretability early

For "Python" specifically:
  Variables/Data Types → Conditionals → Loops → Functions → OOP
  NOT: frameworks or libraries

For any topic: start from ABSOLUTE BASICS and progress naturally.
If days are few, BUNDLE multiple beginner-level subtopics together per day.
If days are many, give each subtopic its own day with more depth.

You must output ONLY a valid JSON object like this:
{{
  "plan": [
    {{
      "day": 1,
      "topic": "ML Fundamentals: What is ML, Types of ML, Key Terminology",
      "description": "Introduction to machine learning, supervised vs unsupervised, key terms like features, labels, model"
    }},
    {{
      "day": 2,
      "topic": "Supervised Learning: Linear Regression and Classification Basics",
      "description": "How supervised learning works, linear regression, logistic regression basics"
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
- Day 1 MUST be absolute basics — no exceptions
- No advanced or niche subtopics (like Model Interpretability, GANs, Transformers) before Day {max(3, learning_days // 2 + 1)}
- Bundle subtopics naturally: "Variables, Data Types and Operators" is fine for one day
- Day {days} = ALWAYS "Practice Test"
- Output ONLY the JSON. No extra text.
"""

def run_planner(days: int = 5) -> dict:
    skill_data = get_value("skill_analysis")
    if not skill_data:
        return None

    topic = skill_data.get("topic", "the topic")
    level = skill_data.get("skill_level", "beginner")

    system_prompt = build_prompt(days)
    user_message  = (
        f"Learner skill analysis: {json.dumps(skill_data, indent=2)}\n\n"
        f"Topic: {topic}\n"
        f"Skill level: {level}\n"
        f"Total days: {days} (including practice test on Day {days})\n"
        f"Learning days available: {days - 1}\n\n"
        f"IMPORTANT RULES:\n"
        f"1. Generate EXACTLY {days} days — not more, not less\n"
        f"2. Day 1 must be absolute beginner basics of {topic}\n"
        f"3. Progress gradually — no advanced topics in early days\n"
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

    # Retry if wrong number of days
    if len(plan) != days:
        print(f"Warning: Got {len(plan)} days, expected {days}. Retrying...")
        response2 = call_llm(system_prompt,
            f"Previous attempt gave wrong number of days.\n"
            f"YOU MUST RETURN EXACTLY {days} DAYS.\n"
            f"Topic: {topic}, Skill level: {level}\n"
            f"Count every item in the plan array — it must equal {days}."
        )
        try:
            result = json.loads(response2.strip().strip("```json").strip("```").strip())
            plan   = result.get("plan", [])
        except json.JSONDecodeError:
            pass

    # Trim if too many
    if len(plan) > days:
        plan = plan[:days]

    # Pad if still too few
    while len(plan) < days:
        plan.append({
            "day": len(plan) + 1,
            "topic": f"{topic} — Continued Practice",
            "description": "Continue practising concepts from previous days"
        })

    # Force correct day numbers
    for i, day in enumerate(plan):
        day["day"] = i + 1

    # Force last day to be Practice Test
    if not any(w in plan[-1]["topic"].lower() for w in ["practice", "revision", "test"]):
        plan[-1]["topic"] = "Practice Test"
        plan[-1]["description"] = "Revise all topics and take a full practice test"

    result["plan"]       = plan
    result["total_days"] = len(plan)

    update_data("total_days", len(plan))
    update_data("study_plan", result)
    return result