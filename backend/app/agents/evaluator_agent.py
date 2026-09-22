import json
from app.core.adaptive import fingerprint
from app.core.llm_client import call_llm
from app.core.logging_config import get_logger
from app.core.prompt_guards import INJECTION_GUARD, wrap_data
from app.storage.json_store import update_data, get_value

logger = get_logger(__name__)

EXPLANATION_PROMPT = f"""
You are an Evaluator Agent for an AI learning coach.
Given a list of questions with the learner's answers and whether they were correct,
provide a short educational explanation for each question.

You must output ONLY a valid JSON object like this:
{{
  "results": [
    {{
      "question_id": 1,
      "explanation": "Correct! A variable is a container for storing data values in memory."
    }},
    {{
      "question_id": 2,
      "explanation": "Incorrect. The correct answer is 'def'. In Python, 'def' is the keyword used to define a function."
    }}
  ],
  "overall_feedback": "one encouraging sentence summarizing the learner's performance"
}}

Output ONLY the JSON. No explanation, no extra text.

{INJECTION_GUARD}
"""

_MAX_CONCEPTS = 10


def _update_concept_stats(session_id: str, qa_for_llm: list, questions_map: dict) -> tuple:
    """Aggregate per-concept correct/wrong counts across the whole session and
    derive weak/strong concept lists for future quiz generation. Pure,
    deterministic Python -- no LLM involved in deciding what's weak/strong."""
    stats = get_value(session_id, "concept_stats") or {}
    for qa in qa_for_llm:
        q = questions_map.get(str(qa["question_id"]), {})
        concept = str(q.get("concept") or "").strip() or "general"
        entry = stats.setdefault(concept, {"correct": 0, "wrong": 0})
        if qa["is_correct"]:
            entry["correct"] += 1
        else:
            entry["wrong"] += 1
    update_data(session_id, "concept_stats", stats)

    weak = sorted(
        (c for c, v in stats.items() if v["wrong"] > v["correct"]),
        key=lambda c: stats[c]["wrong"], reverse=True,
    )[:_MAX_CONCEPTS]
    strong = sorted(
        (c for c, v in stats.items() if v["correct"] > v["wrong"]),
        key=lambda c: stats[c]["correct"], reverse=True,
    )[:_MAX_CONCEPTS]

    update_data(session_id, "weak_concepts", weak)
    update_data(session_id, "strong_concepts", strong)
    return weak, strong


def run_evaluator(session_id: str, answers: dict) -> dict:
    questions_data = get_value(session_id, "current_questions")
    topic = get_value(session_id, "current_topic")

    if not questions_data:
        return {"error": "No questions found", "score": 0, "total": 0, "percentage": 0, "results": []}

    questions = questions_data.get("questions", [])
    if not questions:
        return {"error": "Empty questions", "score": 0, "total": 0, "percentage": 0, "results": []}

    # Map question IDs to question objects
    questions_map = {str(q["id"]): q for q in questions}

    # Score answers directly
    score = 0
    total = len(questions)
    qa_for_llm = []

    for q in questions:
        qid         = str(q["id"])
        correct     = str(q.get("answer", "") or "").strip().upper()
        raw_answer  = answers.get(qid, "")
        # Coerce answer value to string
        learner_ans = str(raw_answer if raw_answer is not None else "").strip().upper()
        is_correct  = learner_ans == correct

        if is_correct:
            score += 1

        qa_for_llm.append({
            "question_id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "learner_answer": learner_ans,
            "correct_answer": correct,
            "is_correct": is_correct
        })

    percentage = round((score / total) * 100) if total > 0 else 0

    # Idempotency guard: a duplicate /evaluate submission for the exact same
    # quiz + the exact same answers (e.g. a double-click before the UI
    # transitions) must not double-count concept stats. A genuinely different
    # answer set for the same quiz still counts normally.
    submission_token = fingerprint({"quiz": fingerprint(questions_data), "answers": answers})
    already_applied = get_value(session_id, "stats_applied_for") == submission_token
    if already_applied:
        weak_concepts = get_value(session_id, "weak_concepts") or []
        strong_concepts = get_value(session_id, "strong_concepts") or []
    else:
        weak_concepts, strong_concepts = _update_concept_stats(session_id, qa_for_llm, questions_map)
        update_data(session_id, "stats_applied_for", submission_token)

    # Generate explanations via LLM
    user_message = (
        f"{wrap_data('Topic', topic)}\n"
        f"{wrap_data('Questions with results', json.dumps(qa_for_llm, indent=2))}"
    )
    response = call_llm(EXPLANATION_PROMPT, user_message)

    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        llm_result = json.loads(cleaned)
    except json.JSONDecodeError:
        llm_result = {
            "results": [{"question_id": q["question_id"], "explanation": ""} for q in qa_for_llm],
            "overall_feedback": ""
        }

    # Combine scores, explanations, and options
    explanations = {
        str(r["question_id"]): r["explanation"]
        for r in llm_result.get("results", [])
    }

    final_results = []
    for q in qa_for_llm:
        qid_str = str(q["question_id"])
        original_q = questions_map.get(qid_str, {})

        final_results.append({
            "question_id":   q["question_id"],
            "type":          q["type"],
            "question":      q["question"],
            "concept":       original_q.get("concept", ""),
            "options":       original_q.get("options", {}),  # Option texts
            "learner_answer": q["learner_answer"],
            "correct_answer": q["correct_answer"],
            "is_correct":    q["is_correct"],
            "explanation":   explanations.get(qid_str, "")
        })

    result = {
        "score":            score,
        "total":            total,
        "percentage":       percentage,
        "results":          final_results,
        "overall_feedback": llm_result.get("overall_feedback", ""),
        "weak_concepts":    weak_concepts,
        "strong_concepts":  strong_concepts,
    }

    update_data(session_id, "evaluation", result)
    update_data(session_id, "evaluation_token", fingerprint(final_results))
    return result
    