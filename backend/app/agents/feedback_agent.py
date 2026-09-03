import json
from app.core.llm_client import call_llm
from app.storage.json_store import update_data, get_value

SYSTEM_PROMPT = """
You are a Feedback and Decision Agent for an AI learning coach.
Based on the learner's evaluation results, decide what they should do next.

You must output ONLY a valid JSON object like this:
{
  "decision": "next_topic",
  "feedback": "encouraging 2-3 sentence feedback message for the learner",
  "reason": "why you made this decision"
}

Decision rules:
- Score >= 70%: decision = "next_topic"
- Score 50-69%: decision = "repeat_topic"
- Score < 50%:  decision = "revise_topic"

Output ONLY the JSON. No explanation, no extra text.
"""

PRACTICE_REPORT_PROMPT = """
You are a Learning Coach giving a final performance summary after a practice test.

Based on the learner's results, generate a short but useful performance report.

You must output ONLY a valid JSON object like this:
{
  "summary": "2-3 sentence overall summary of their performance",
  "strengths": ["one strength", "another strength"],
  "improvements": ["one specific area to improve", "another area"],
  "next_steps": "One motivating sentence about what to study next"
}

Rules:
- strengths: 1-3 items, specific to what they got right
- improvements: 1-3 items, specific topics they got wrong, be direct and helpful
- Keep everything concise and actionable
- Output ONLY the JSON. No explanation, no extra text.
"""


def get_next_topic_by_day(session_id: str, completed_day: int):
    """Return the next day's topic, or None if plan is complete."""
    plan_data = get_value(session_id, "study_plan")
    if not plan_data:
        return None

    plan = plan_data.get("plan", [])
    next_day_num = completed_day + 1

    for day in plan:
        if day["day"] == next_day_num:
            return day["topic"]

    return None  # No more days


def get_grade(percentage: int) -> str:
    if percentage >= 95: return "A+"
    if percentage >= 85: return "A"
    if percentage >= 75: return "B+"
    if percentage >= 65: return "B"
    if percentage >= 55: return "C+"
    if percentage >= 45: return "C"
    if percentage >= 35: return "D"
    return "F"


def run_practice_report(evaluation: dict, skill_data: dict) -> dict:
    wrong = [r for r in evaluation.get("results", []) if not r["is_correct"]]
    right = [r for r in evaluation.get("results", []) if r["is_correct"]]

    user_message = f"""
Topic: {skill_data.get("topic", "Unknown") if skill_data else "Unknown"}
Score: {evaluation.get("score")}/{evaluation.get("total")} ({evaluation.get("percentage")}%)

Correct answers ({len(right)}):
{json.dumps([r["question"] for r in right], indent=2)}

Wrong answers ({len(wrong)}):
{json.dumps([{
    "question": r["question"],
    "learner_answer": r["learner_answer"],
    "correct_answer": r["correct_answer"],
    "explanation": r.get("explanation", "")
} for r in wrong], indent=2)}
"""
    response = call_llm(PRACTICE_REPORT_PROMPT, user_message)
    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        report  = json.loads(cleaned)
    except json.JSONDecodeError:
        report = {
            "summary": evaluation.get("overall_feedback", "You completed the practice test!"),
            "strengths": ["Completing the full study plan"],
            "improvements": [r["question"] for r in wrong[:3]],
            "next_steps": "Review the topics where you made mistakes and try again!"
        }

    report["grade"]      = get_grade(evaluation.get("percentage", 0))
    report["score"]      = evaluation.get("score")
    report["total"]      = evaluation.get("total")
    report["percentage"] = evaluation.get("percentage")
    return report


def run_feedback_agent(session_id: str) -> dict:
    evaluation = get_value(session_id, "evaluation")
    current    = get_value(session_id, "current_topic")
    skill_data = get_value(session_id, "skill_analysis")

    if not evaluation:
        return {"decision": "repeat_topic", "feedback": "", "reason": "", "next_topic": current}

    # Current day index
    saved_day    = get_value(session_id, "current_day") or 0
    is_practice  = "practice" in (current or "").lower()

    # Check for next day in plan
    next_topic_preview = get_next_topic_by_day(session_id, saved_day)
    is_last_day        = (next_topic_preview is None) and not is_practice

    if is_practice or is_last_day:
        report = run_practice_report(evaluation, skill_data)
        result = {
            "decision":   "complete",
            "next_topic": None,
            "feedback":   report.get("summary", ""),
            "report":     report
        }
        update_data(session_id, "feedback", result)
        update_data(session_id, "final_report", report)
        return result

    # Get LLM progression decision
    user_message = f"""
Current topic: {current}
Evaluation results: {json.dumps(evaluation, indent=2)}
"""
    response = call_llm(SYSTEM_PROMPT, user_message)

    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        result  = json.loads(cleaned)
    except json.JSONDecodeError:
        result  = {"decision": "repeat_topic", "feedback": "", "reason": ""}

    decision = result.get("decision")

    if decision == "next_topic":
        # Advance to next day index
        next_day   = saved_day + 1
        update_data(session_id, "current_day", next_day)

        next_topic = get_next_topic_by_day(session_id, next_day)
        result["next_topic"] = next_topic

        # Persist next topic for subsequent requests
        if next_topic:
            update_data(session_id, "current_topic", next_topic)

    else:
        # Keep current topic and day on repeat or revise
        result["next_topic"] = current

    update_data(session_id, "feedback", result)
    return result
