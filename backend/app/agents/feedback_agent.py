import json
from app.core.adaptive import (
    DAY_TYPE_PRACTICE_TEST,
    adjust_difficulty,
    compute_difficulty_decision,
    compute_topic_decision,
    day_type_of,
    find_day,
    fingerprint,
    resolve_day_type,
)
from app.core.llm_client import call_llm
from app.core.prompt_guards import INJECTION_GUARD, wrap_data
from app.storage.json_store import update_data, get_value

SYSTEM_PROMPT = f"""
You are a Feedback Agent for an AI learning coach.
The learner's topic progression and difficulty progression have ALREADY been
decided by the app (deterministically, from their score) -- your only job is
to write a short, encouraging message consistent with those decisions.

You must output ONLY a valid JSON object like this:
{{
  "feedback": "encouraging 2-3 sentence feedback message for the learner",
  "reason": "one sentence on why, referencing their score"
}}

Rules:
- NEVER contradict the topic_decision or difficulty_decision given to you.
- Do not invent a different decision -- only explain/encourage around the
  ones you were given.
- Output ONLY the JSON. No explanation, no extra text.

{INJECTION_GUARD}
"""

PRACTICE_REPORT_PROMPT = f"""
You are a Learning Coach giving a final performance summary after a practice test.

Based on the learner's results, generate a short but useful performance report.

You must output ONLY a valid JSON object like this:
{{
  "summary": "2-3 sentence overall summary of their performance",
  "strengths": ["one strength", "another strength"],
  "improvements": ["one specific area to improve", "another area"],
  "next_steps": "One motivating sentence about what to study next"
}}

Rules:
- strengths: 1-3 items, specific to what they got right
- improvements: 1-3 items, specific topics they got wrong, be direct and helpful
- Keep everything concise and actionable
- Output ONLY the JSON. No explanation, no extra text.

{INJECTION_GUARD}
"""

_FALLBACK_FEEDBACK = {
    "next_topic":   "Nice work -- you're ready to move on to the next topic!",
    "repeat_topic": "You're close. Let's go over this topic once more with a bit more guidance.",
    "revise_topic": "This one needs more review -- let's revisit the fundamentals before continuing.",
}


def get_next_day_info(session_id: str, completed_day: int):
    """Return (topic, day_type) for the day after completed_day, or (None, None)."""
    plan_data = get_value(session_id, "study_plan")
    day = find_day(plan_data, completed_day + 1)
    if not day:
        return None, None
    return day["topic"], day_type_of(day)


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
{wrap_data('Topic', skill_data.get("topic", "Unknown") if skill_data else "Unknown")}
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
        return {
            "decision": "repeat_topic", "difficulty_decision": "maintain",
            "feedback": "", "reason": "", "next_topic": current,
        }

    # Idempotency guard: a duplicate /feedback POST for the same evaluation
    # (e.g. a double-click before the UI transitions) must return the same
    # cached result rather than re-running LLM calls, re-advancing the day,
    # or re-adjusting difficulty a second time.
    eval_token = get_value(session_id, "evaluation_token") or fingerprint(evaluation)
    if get_value(session_id, "last_feedback_token") == eval_token:
        cached = get_value(session_id, "feedback")
        if cached:
            return cached

    percentage = evaluation.get("percentage", 0)

    # Topic progression and difficulty progression are deterministic, pure
    # Python functions of the score -- kept intentionally separate from each
    # other, and never left to the LLM to decide.
    topic_decision      = compute_topic_decision(percentage)
    difficulty_decision = compute_difficulty_decision(percentage)

    current_difficulty = get_value(session_id, "difficulty") or (
        skill_data.get("skill_level", "beginner") if skill_data else "beginner"
    )
    new_difficulty = adjust_difficulty(current_difficulty, difficulty_decision)
    update_data(session_id, "difficulty", new_difficulty)

    saved_day = get_value(session_id, "current_day") or 0
    plan_data = get_value(session_id, "study_plan")
    stored_day_type = get_value(session_id, "current_day_type")
    day_type = resolve_day_type(stored_day_type, plan_data, saved_day + 1)
    is_practice = day_type == DAY_TYPE_PRACTICE_TEST

    # Is there a day after the one just evaluated? (Defensive fallback for a
    # plan that somehow ends without its last day being flagged practice_test.)
    topic_after_current, _ = get_next_day_info(session_id, saved_day + 1)
    is_last_day = (topic_after_current is None) and not is_practice

    if is_practice or is_last_day:
        report = run_practice_report(evaluation, skill_data)
        report["weak_concepts"]   = evaluation.get("weak_concepts", [])
        report["strong_concepts"] = evaluation.get("strong_concepts", [])
        result = {
            "decision":            "complete",
            "difficulty_decision": difficulty_decision,
            "difficulty":          new_difficulty,
            "next_topic":          None,
            "feedback":            report.get("summary", ""),
            "report":              report,
        }
        update_data(session_id, "feedback", result)
        update_data(session_id, "final_report", report)
        update_data(session_id, "last_feedback_token", eval_token)
        return result

    # LLM writes only the encouraging message text -- it is told the
    # already-decided outcome and must not contradict it.
    user_message = f"""{wrap_data('Current topic', current)}
topic_decision (already determined -- explain/encourage, do not change): {topic_decision}
difficulty_decision (already determined -- explain/encourage, do not change): {difficulty_decision}
Score: {evaluation.get('score')}/{evaluation.get('total')} ({percentage}%)
"""
    response = call_llm(SYSTEM_PROMPT, user_message)
    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        llm_result = json.loads(cleaned)
    except json.JSONDecodeError:
        llm_result = {}

    result = {
        "decision":            topic_decision,
        "difficulty_decision": difficulty_decision,
        "difficulty":          new_difficulty,
        "feedback":            llm_result.get("feedback") or _FALLBACK_FEEDBACK.get(topic_decision, ""),
        "reason":              llm_result.get("reason", ""),
    }

    if topic_decision == "next_topic":
        next_day = saved_day + 1
        update_data(session_id, "current_day", next_day)

        next_topic, next_day_type = get_next_day_info(session_id, next_day)
        result["next_topic"] = next_topic

        if next_topic:
            update_data(session_id, "current_topic", next_topic)
            update_data(session_id, "current_day_type", next_day_type or DAY_TYPE_PRACTICE_TEST)
    else:
        # Keep current topic and day on repeat or revise
        result["next_topic"] = current

    update_data(session_id, "feedback", result)
    update_data(session_id, "last_feedback_token", eval_token)
    return result
    