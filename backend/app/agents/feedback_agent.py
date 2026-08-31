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


def get_next_topic_by_day(completed_day: int):
    """
    Pure index-based lookup — no string matching.
    Pass the day number just completed; returns topic for the NEXT day.
    Returns None when there are no more days (plan complete).
    """
    plan_data = get_value("study_plan")
    if not plan_data:
        return None

    plan = plan_data.get("plan", [])
    next_day_num = completed_day + 1

    for day in plan:
        if day["day"] == next_day_num:
            return day["topic"]

    return None  # no more days


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


def run_feedback_agent() -> dict:
    evaluation = get_value("evaluation")
    current    = get_value("current_topic")
    skill_data = get_value("skill_analysis")

    if not evaluation:
        return {"decision": "repeat_topic", "feedback": "", "reason": "", "next_topic": current}

    # Read the current saved day ONCE — used throughout this function
    saved_day    = get_value("current_day") or 0
    is_practice  = "practice" in (current or "").lower()

    # Check if next day exists (index-based, no string matching)
    next_topic_preview = get_next_topic_by_day(saved_day)
    is_last_day        = (next_topic_preview is None) and not is_practice

    if is_practice or is_last_day:
        report = run_practice_report(evaluation, skill_data)
        result = {
            "decision":   "complete",
            "next_topic": None,
            "feedback":   report.get("summary", ""),
            "report":     report
        }
        update_data("feedback", result)
        update_data("final_report", report)
        return result

    # Normal day: ask LLM for pass / repeat / revise decision
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
        # ✅ FIX 1: increment day FIRST, then look up the topic for that new day
        next_day   = saved_day + 1
        update_data("current_day", next_day)           # save the day we're moving TO

        next_topic = get_next_topic_by_day(next_day)   # look up topic for next_day + 1
        result["next_topic"] = next_topic

        # ✅ FIX 2: persist next_topic on backend so /questions always serves correct topic
        # (main.py reads current_topic from the file, ignoring req.topic)
        if next_topic:
            update_data("current_topic", next_topic)

    else:
        # repeat_topic or revise_topic — stay on same topic, don't advance day
        result["next_topic"] = current

    update_data("feedback", result)
    return result