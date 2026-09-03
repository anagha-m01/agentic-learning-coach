import json
from app.core.llm_client import call_llm
from app.storage.json_store import update_data, get_value

EXPLANATION_PROMPT = """
You are an Evaluator Agent for an AI learning coach.
Given a list of questions with the learner's answers and whether they were correct,
provide a short educational explanation for each question.

You must output ONLY a valid JSON object like this:
{
  "results": [
    {
      "question_id": 1,
      "explanation": "Correct! A variable is a container for storing data values in memory."
    },
    {
      "question_id": 2,
      "explanation": "Incorrect. The correct answer is 'def'. In Python, 'def' is the keyword used to define a function."
    }
  ],
  "overall_feedback": "one encouraging sentence summarizing the learner's performance"
}

Output ONLY the JSON. No explanation, no extra text.
"""

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

    # Generate explanations via LLM
    user_message = f"Topic: {topic}\nQuestions with results:\n{json.dumps(qa_for_llm, indent=2)}"
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
        "overall_feedback": llm_result.get("overall_feedback", "")
    }

    update_data(session_id, "evaluation", result)
    return result
