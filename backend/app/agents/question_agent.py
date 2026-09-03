import json
from app.core.llm_client import call_llm
from app.core.logging_config import get_logger
from app.storage.json_store import update_data, get_value

logger = get_logger(__name__)

SYSTEM_PROMPT = """
You are a Question Generator Agent for an AI learning coach.
Create ONLY multiple choice questions. Every single question MUST have exactly 4 options: A, B, C, D.

You must output ONLY a valid JSON object like this:
{
  "topic": "the topic being tested",
  "questions": [
    {
      "id": 1,
      "type": "mcq",
      "question": "What is a variable in Python?",
      "options": {
        "A": "A fixed value that cannot change",
        "B": "A container for storing data values",
        "C": "A type of loop",
        "D": "A built-in function"
      },
      "answer": "B"
    },
    {
      "id": 2,
      "type": "code_output",
      "question": "What is the output of the following code?",
      "code": "x = [1, 2, 3]\\nprint(x[1])",
      "options": {
        "A": "1",
        "B": "2",
        "C": "3",
        "D": "Error"
      },
      "answer": "B"
    }
  ]
}

STRICT RULES — violations will break the app:
1. Generate EXACTLY 6 questions
2. EVERY question MUST have "options" with keys A, B, C, D — no exceptions
3. EVERY question MUST have "answer" set to one of: A, B, C, or D
4. "mcq" type = concept question with 4 answer choices
5. "code_output" type = show a short code snippet, ask "What is the output?" with 4 answer choices
6. NEVER generate open-ended questions like "Write a code snippet..." or "Explain..."
7. NEVER generate questions without options — every question is multiple choice
8. code snippets must be max 5 lines, use \\n for newlines
9. Output ONLY the JSON. No explanation, no extra text.
"""

def get_question_distribution(day_number: int, total_days: int) -> tuple:
    if total_days <= 1:
        return (6, 0)
    progress = (day_number - 1) / (total_days - 1)
    if progress == 0:
        return (6, 0)
    elif progress < 0.4:
        return (6, 0)
    elif progress < 0.7:
        return (4, 2)
    else:
        return (3, 3)

def get_topic_mix_instruction(day_number: int, total_days: int, plan_data: dict) -> str:
    if not plan_data:
        return ""
    plan = plan_data.get("plan", [])
    previous_topics = []
    for day in plan:
        if day["day"] < day_number and "practice" not in day["topic"].lower():
            previous_topics.append(f"Day {day['day']}: {day['topic']}")
    if not previous_topics:
        return "Focus only on today's topic."
    learning_days = total_days - 1
    if learning_days <= 2:
        mix_ratio = "4 questions from previous topics, 2 from today's topic"
    elif learning_days <= 4:
        if day_number == 2:
            mix_ratio = "3 questions from previous topics, 3 from today's topic"
        else:
            mix_ratio = "4 questions from previous topics, 2 from today's topic"
    else:
        progress = (day_number - 1) / (total_days - 1)
        if progress < 0.4:
            mix_ratio = "1 question from previous topics, 5 from today's topic"
        elif progress < 0.7:
            mix_ratio = "2 questions from previous topics, 4 from today's topic"
        else:
            mix_ratio = "3 questions from previous topics, 3 from today's topic"
    previous_list = "\n".join(previous_topics)
    return (
        f"Topic mixing instruction: {mix_ratio}\n"
        f"Previous topics to pull questions from:\n{previous_list}"
    )

def is_valid_mcq(q: dict) -> bool:
    """Validate question has required MCQ options and answer."""
    options = q.get("options", {})
    answer  = q.get("answer", "").strip().upper()
    return (
        isinstance(options, dict)
        and all(k in options for k in ["A", "B", "C", "D"])
        and answer in ["A", "B", "C", "D"]
        and bool(q.get("question", "").strip())
    )

def is_open_ended(q: dict) -> bool:
    """Check whether a question is open-ended."""
    bad_phrases = [
        "write a", "write the", "implement", "create a", "code a",
        "develop a", "build a", "program a", "design a", "construct a",
        "explain how", "describe how", "list the steps"
    ]
    question_text = q.get("question", "").lower()
    # Missing options implies open-ended
    if not q.get("options"):
        return True
    # Check forbidden prefix phrases
    return any(question_text.startswith(phrase) for phrase in bad_phrases)

def fix_question_numbering(questions: list) -> list:
    """Ensure sequential question IDs."""
    for i, q in enumerate(questions):
        q["id"] = i + 1
    return questions

def run_question_generator(session_id: str, current_topic: str = None) -> dict:
    skill_data  = get_value(session_id, "skill_analysis")
    current_day = get_value(session_id, "current_day") or 0
    plan_data   = get_value(session_id, "study_plan")
    total_days  = get_value(session_id, "total_days") or 5

    day_number = current_day + 1

    if not current_topic:
        current_topic = skill_data.get("starting_topic", "the basics") if skill_data else "the basics"

    level = skill_data.get("skill_level", "beginner") if skill_data else "beginner"

    concept_count, code_count = get_question_distribution(day_number, total_days)
    mix_instruction = get_topic_mix_instruction(day_number, total_days, plan_data)

    previous_topics = []
    if plan_data:
        for day in plan_data.get("plan", []):
            if day["day"] < day_number and "practice" not in day["topic"].lower():
                previous_topics.append(f"Day {day['day']}: {day['topic']}")

    is_practice_test = "practice" in current_topic.lower()

    if is_practice_test and previous_topics:
        user_message = f"""Topic: {current_topic}
Skill level: {level}
Day number: {day_number} out of {total_days}
Question types: {concept_count} concept MCQ and {code_count} code output MCQ

IMPORTANT: ALL 6 questions must be multiple choice with options A, B, C, D.
code_output = show a short code snippet and ask what the output is (still MCQ).
NEVER ask the learner to write code. NEVER generate open-ended questions.

This is the PRACTICE TEST day. Generate 6 revision MCQ questions covering ALL these topics:
{chr(10).join(previous_topics)}"""

    else:
        user_message = f"""Topic: {current_topic}
Skill level: {level}
Day number: {day_number} out of {total_days}
Question types: {concept_count} concept MCQ and {code_count} code output MCQ

IMPORTANT: ALL 6 questions must be multiple choice with options A, B, C, D.
code_output = show a short code snippet (max 5 lines) and ask "What is the output?" (still MCQ).
NEVER ask the learner to write code. NEVER generate open-ended questions.

Today's topic: {current_topic}
{mix_instruction}

Generate exactly {concept_count} concept MCQ and {code_count} code output MCQ questions."""

    response = call_llm(SYSTEM_PROMPT, user_message)

    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        result  = json.loads(cleaned)
    except json.JSONDecodeError:
        result  = {"topic": current_topic, "questions": []}

    questions = result.get("questions", [])

    # Post-processing validation
    # Ensure day 1 has no code output questions
    if day_number == 1:
        for q in questions:
            if q.get("type") == "code_output":
                q["type"] = "mcq"
                q.pop("code", None)

    # Remove open-ended questions
    questions = [q for q in questions if not is_open_ended(q)]

    # Filter out invalid MCQs
    questions = [q for q in questions if is_valid_mcq(q)]

    # Retry prompt if question count is insufficient
    if len(questions) < 6:
        logger.warning(f"question_agent: only {len(questions)} valid MCQ after filtering, retrying")
        retry_message = (
            f"Previous attempt produced invalid questions (open-ended or missing options).\n"
            f"Topic: {current_topic}, Skill level: {level}\n"
            f"YOU MUST generate exactly 6 multiple choice questions.\n"
            f"Every question MUST have options A, B, C, D and a single letter answer.\n"
            f"DO NOT generate any question that asks the learner to write or implement code.\n"
            f"code_output type = show existing code snippet, ask what it outputs, give 4 MCQ options."
        )
        retry_response = call_llm(SYSTEM_PROMPT, retry_message)
        try:
            retry_cleaned = retry_response.strip().strip("```json").strip("```").strip()
            retry_result  = json.loads(retry_cleaned)
            retry_qs      = retry_result.get("questions", [])
            retry_qs      = [q for q in retry_qs if not is_open_ended(q)]
            retry_qs      = [q for q in retry_qs if is_valid_mcq(q)]
            # Merge valid questions from retry
            existing_ids = {q.get("id") for q in questions}
            for q in retry_qs:
                if len(questions) >= 6:
                    break
                if q.get("id") not in existing_ids:
                    questions.append(q)
        except json.JSONDecodeError:
            pass

    # Cap at 6 questions and renumber
    questions = questions[:6]
    questions = fix_question_numbering(questions)

    result["questions"] = questions
    update_data(session_id, "current_questions", result)
    update_data(session_id, "current_topic", current_topic)
    return result
