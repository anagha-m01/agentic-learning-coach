import json
from app.core.adaptive import (
    DAY_TYPE_PRACTICE_TEST,
    day_type_of,
    is_near_duplicate,
    normalize_question_text,
    resolve_day_type,
)
from app.core.llm_client import call_llm
from app.core.logging_config import get_logger
from app.core.prompt_guards import INJECTION_GUARD, wrap_data
from app.storage.json_store import update_data, get_value

logger = get_logger(__name__)

# How much a difficulty tier should shape question style. Kept intentionally
# separate from topic content -- this only changes HOW hard/tricky questions
# on the given topic are, never WHAT topic is being tested.
LEVEL_QUESTION_GUIDANCE = {
    "beginner": (
        "Use simple, explicit language. Test recognition of definitions and "
        "basic mechanics. Avoid tricky wording, edge cases, or advanced jargon."
    ),
    "intermediate": (
        "Assume comfort with the basics. Test how concepts connect, common "
        "pitfalls, and moderately tricky but fair scenarios."
    ),
    "advanced": (
        "Test deeper understanding: edge cases, subtle gotchas, trade-offs, "
        "and nuanced distinctions between similar concepts. Fair, but not easy."
    ),
}

# History of previously asked questions and known weak/strong concepts are
# capped so the prompt doesn't grow unbounded over a long study plan.
_MAX_ASKED_HISTORY = 80
_MAX_ASKED_IN_PROMPT = 15
_MAX_CONCEPTS_IN_PROMPT = 10

SYSTEM_PROMPT = f"""
You are a Question Generator Agent for an AI learning coach.
Create ONLY multiple choice questions. Every single question MUST have exactly 4 options: A, B, C, D.

You must output ONLY a valid JSON object like this:
{{
  "topic": "the topic being tested",
  "questions": [
    {{
      "id": 1,
      "type": "mcq",
      "question": "What is a variable in Python?",
      "concept": "variables",
      "options": {{
        "A": "A fixed value that cannot change",
        "B": "A container for storing data values",
        "C": "A type of loop",
        "D": "A built-in function"
      }},
      "answer": "B"
    }},
    {{
      "id": 2,
      "type": "code_output",
      "question": "What is the output of the following code?",
      "concept": "list indexing",
      "code": "x = [1, 2, 3]\\nprint(x[1])",
      "options": {{
        "A": "1",
        "B": "2",
        "C": "3",
        "D": "Error"
      }},
      "answer": "B"
    }}
  ]
}}

STRICT RULES — violations will break the app:
1. Generate EXACTLY 6 questions
2. EVERY question MUST have "options" with keys A, B, C, D — no exceptions
3. Every option value must be non-empty and DISTINCT from the other three options
4. EVERY question MUST have "answer" set to one of: A, B, C, or D
5. EVERY question MUST have a "concept" field: a short (1-4 word) tag naming the
   exact concept being tested (e.g. "for loops", "list slicing"), not the whole topic
6. "mcq" type = concept question with 4 answer choices
7. "code_output" type = show a short code snippet, ask "What is the output?" with 4 answer choices
8. NEVER generate open-ended questions like "Write a code snippet..." or "Explain..."
9. NEVER generate questions without options — every question is multiple choice
10. code snippets must be max 5 lines, use \\n for newlines
11. Do NOT repeat or closely rephrase any question listed as already asked
12. Output ONLY the JSON. No explanation, no extra text.

{INJECTION_GUARD}
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
        if day["day"] < day_number and day_type_of(day) != DAY_TYPE_PRACTICE_TEST:
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
    """Validate question has required MCQ options (non-empty, distinct) and answer."""
    options = q.get("options", {})
    answer  = str(q.get("answer", "") or "").strip().upper()
    if not isinstance(options, dict) or not all(k in options for k in ["A", "B", "C", "D"]):
        return False
    values = []
    for k in ["A", "B", "C", "D"]:
        v = str(options.get(k, "") or "").strip()
        if not v:
            return False
        values.append(v.lower())
    if len(set(values)) != len(values):
        return False  # duplicate option text -> ambiguous / broken question
    if answer not in ["A", "B", "C", "D"]:
        return False
    return bool(str(q.get("question", "")).strip())


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


def _clean_and_validate(raw_questions: list, current_topic: str, day_number: int,
                         history_normalized: list, accepted_normalized: list) -> list:
    """Apply type coercion, MCQ validation, and duplicate filtering in one pass.
    Mutates accepted_normalized as a side effect so repeated calls (initial +
    retry) dedupe against each other, not just against prior sessions."""
    kept = []
    for q in raw_questions:
        if is_open_ended(q):
            continue

        # A code_output question with no actual code isn't valid as code_output;
        # downgrade rather than discard an otherwise-usable question.
        if q.get("type") == "code_output" and not str(q.get("code") or "").strip():
            q["type"] = "mcq"
            q.pop("code", None)

        # Day 1 never shows code -- learner has no foundation to read it yet.
        if day_number == 1 and q.get("type") == "code_output":
            q["type"] = "mcq"
            q.pop("code", None)

        if not is_valid_mcq(q):
            continue

        if not str(q.get("concept", "")).strip():
            q["concept"] = current_topic

        qtext = q.get("question", "")
        if is_near_duplicate(qtext, history_normalized) or is_near_duplicate(qtext, accepted_normalized):
            continue

        accepted_normalized.append(normalize_question_text(qtext))
        kept.append(q)
    return kept


def run_question_generator(session_id: str, current_topic: str = None) -> dict:
    skill_data  = get_value(session_id, "skill_analysis")
    current_day = get_value(session_id, "current_day") or 0
    plan_data   = get_value(session_id, "study_plan")
    total_days  = get_value(session_id, "total_days") or 5

    day_number = current_day + 1

    if not current_topic:
        current_topic = skill_data.get("starting_topic", "the basics") if skill_data else "the basics"

    # The learner's own selected level, adapted after each quiz -- distinct
    # from skill_analysis["skill_level"], which is never modified after intake.
    level = get_value(session_id, "difficulty") or (
        skill_data.get("skill_level", "beginner") if skill_data else "beginner"
    )
    goal = skill_data.get("goal") if skill_data else None

    weak_concepts   = (get_value(session_id, "weak_concepts") or [])[:_MAX_CONCEPTS_IN_PROMPT]
    strong_concepts = (get_value(session_id, "strong_concepts") or [])[:_MAX_CONCEPTS_IN_PROMPT]
    asked_questions = get_value(session_id, "asked_questions") or []

    concept_count, code_count = get_question_distribution(day_number, total_days)
    mix_instruction = get_topic_mix_instruction(day_number, total_days, plan_data)

    stored_day_type = get_value(session_id, "current_day_type")
    day_type = resolve_day_type(stored_day_type, plan_data, day_number)
    is_practice_test = day_type == DAY_TYPE_PRACTICE_TEST

    previous_topics = []
    if plan_data:
        for day in plan_data.get("plan", []):
            if day["day"] < day_number and day_type_of(day) != DAY_TYPE_PRACTICE_TEST:
                previous_topics.append(f"Day {day['day']}: {day['topic']}")

    level_guidance = LEVEL_QUESTION_GUIDANCE.get(level, LEVEL_QUESTION_GUIDANCE["beginner"])
    difficulty_block = f"Difficulty target: {level}\n{level_guidance}"

    extra_blocks = [difficulty_block]
    if goal:
        extra_blocks.append(wrap_data(
            "Learner's stated goal (let it inform question style/scenarios where "
            "natural -- e.g. interview prep vs. hands-on project -- without "
            "changing the topic or difficulty target)",
            goal,
        ))
    if weak_concepts:
        extra_blocks.append(wrap_data(
            "Learner's known weak concepts from past quizzes (prioritize "
            "testing these again where relevant to today's topic)",
            ", ".join(weak_concepts),
        ))
    if strong_concepts:
        extra_blocks.append(wrap_data(
            "Learner's known strong concepts (already solid -- don't over-test these)",
            ", ".join(strong_concepts),
        ))
    if asked_questions:
        extra_blocks.append(wrap_data(
            "Questions already asked in previous quizzes -- do not repeat or "
            "closely rephrase any of these",
            "\n".join(asked_questions[-_MAX_ASKED_IN_PROMPT:]),
        ))
    extra_context = "\n\n".join(extra_blocks)

    if is_practice_test and previous_topics:
        user_message = f"""{wrap_data('Topic', current_topic)}
Skill level: {level}
Day number: {day_number} out of {total_days}
Question types: {concept_count} concept MCQ and {code_count} code output MCQ

IMPORTANT: ALL 6 questions must be multiple choice with options A, B, C, D.
code_output = show a short code snippet and ask what the output is (still MCQ).
NEVER ask the learner to write code. NEVER generate open-ended questions.

This is the PRACTICE TEST day. Generate 6 revision MCQ questions covering ALL these topics:
{chr(10).join(previous_topics)}

{extra_context}"""

    else:
        user_message = f"""{wrap_data('Topic', current_topic)}
Skill level: {level}
Day number: {day_number} out of {total_days}
Question types: {concept_count} concept MCQ and {code_count} code output MCQ

IMPORTANT: ALL 6 questions must be multiple choice with options A, B, C, D.
code_output = show a short code snippet (max 5 lines) and ask "What is the output?" (still MCQ).
NEVER ask the learner to write code. NEVER generate open-ended questions.

Today's topic: {current_topic}
{mix_instruction}

Generate exactly {concept_count} concept MCQ and {code_count} code output MCQ questions.

{extra_context}"""

    response = call_llm(SYSTEM_PROMPT, user_message)

    try:
        cleaned = response.strip().strip("```json").strip("```").strip()
        result  = json.loads(cleaned)
    except json.JSONDecodeError:
        result  = {"topic": current_topic, "questions": []}

    history_normalized  = [normalize_question_text(t) for t in asked_questions]
    accepted_normalized = []
    questions = _clean_and_validate(
        result.get("questions", []), current_topic, day_number,
        history_normalized, accepted_normalized,
    )

    # Retry prompt if question count is insufficient (malformed, open-ended,
    # invalid MCQs, or duplicates were filtered out)
    if len(questions) < 6:
        logger.warning(f"question_agent: only {len(questions)} valid MCQ after filtering, retrying")
        retry_message = (
            f"Previous attempt produced invalid, duplicate, or open-ended questions.\n"
            f"{wrap_data('Topic', current_topic)}\n"
            f"Skill level: {level}\n"
            f"YOU MUST generate exactly 6 NEW multiple choice questions, none of them "
            f"duplicates or close rephrasings of ones already listed as asked.\n"
            f"Every question MUST have options A, B, C, D (all distinct, non-empty), "
            f"a single letter answer, and a short 'concept' tag.\n"
            f"DO NOT generate any question that asks the learner to write or implement code.\n"
            f"code_output type = show existing code snippet, ask what it outputs, give 4 MCQ options.\n\n"
            f"{extra_context}"
        )
        retry_response = call_llm(SYSTEM_PROMPT, retry_message)
        try:
            retry_cleaned = retry_response.strip().strip("```json").strip("```").strip()
            retry_result  = json.loads(retry_cleaned)
            retry_qs      = _clean_and_validate(
                retry_result.get("questions", []), current_topic, day_number,
                history_normalized, accepted_normalized,
            )
            # Merge valid questions from retry
            existing_ids = {q.get("id") for q in questions}
            for q in retry_qs:
                if len(questions) >= 6:
                    break
                if q.get("id") not in existing_ids:
                    questions.append(q)
                    existing_ids.add(q.get("id"))
        except json.JSONDecodeError:
            pass

    # Cap at 6 questions and renumber
    questions = questions[:6]
    questions = fix_question_numbering(questions)

    # Remember these questions were asked so future quizzes (this session)
    # don't repeat or closely rephrase them.
    if questions:
        updated_history = (asked_questions + [q.get("question", "") for q in questions])[-_MAX_ASKED_HISTORY:]
        update_data(session_id, "asked_questions", updated_history)

    result["questions"]  = questions
    result["day_type"]   = day_type
    result["difficulty"] = level
    result["is_partial"] = len(questions) < 6
    update_data(session_id, "current_questions", result)
    update_data(session_id, "current_topic", current_topic)
    update_data(session_id, "current_day_type", day_type)
    return result
    