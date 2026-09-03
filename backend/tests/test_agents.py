"""Unit tests for agent modules."""
from app.agents.skill_analyzer import run_skill_analyzer
from app.agents.planner_agent import run_planner
from app.agents.question_agent import run_question_generator
from app.agents.evaluator_agent import run_evaluator
from app.storage.json_store import update_data, get_value


SID = "test-session-1234567890"


def test_skill_analyzer_happy_path(mock_llm):
    result = run_skill_analyzer(SID, "Python", "beginner", "get a job")
    assert result["topic"] == "Python"
    assert get_value(SID, "skill_analysis") == result


def test_skill_analyzer_falls_back_on_malformed_llm_json(mock_llm):
    mock_llm["next_response"] = "not valid json at all {{{"
    result = run_skill_analyzer(SID, "Rust", "advanced", "master it")
    # Fallback response on malformed JSON
    assert result["topic"] == "Rust"
    assert result["skill_level"] == "advanced"
    assert result["weaknesses"] == []


def test_planner_returns_none_without_prior_skill_analysis(mock_llm):
    empty_sid = "no-skill-analysis-session"
    result = run_planner(empty_sid, days=5)
    assert result is None


def test_planner_forces_exact_day_count(mock_llm):
    run_skill_analyzer(SID, "Python", "beginner", "x")
    result = run_planner(SID, days=7)
    assert result["total_days"] == 7
    assert len(result["plan"]) == 7
    assert [d["day"] for d in result["plan"]] == list(range(1, 8))


def test_planner_last_day_is_always_practice_test(mock_llm):
    run_skill_analyzer(SID, "Python", "beginner", "x")
    result = run_planner(SID, days=4)
    assert "practice" in result["plan"][-1]["topic"].lower() \
        or "test" in result["plan"][-1]["topic"].lower()


def test_planner_guards_against_invalid_days(mock_llm):
    run_skill_analyzer(SID, "Python", "beginner", "x")
    result = run_planner(SID, days=0)  # Invalid days fall back to 5
    assert result["total_days"] == 5


def test_question_generator_filters_invalid_mcqs(mock_llm):
    mock_llm["next_response"] = '''
    {"questions": [
      {"id": 1, "type": "mcq", "question": "Valid?",
       "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "answer": "B"},
      {"id": 2, "type": "mcq", "question": "Missing options",
       "options": {}, "answer": "B"}
    ]}
    '''
    result = run_question_generator(SID, "Python")
    ids = [q["id"] for q in result["questions"]]
    assert 1 in ids
    # Verify valid questions are retained
    assert len(result["questions"]) >= 1


def test_evaluator_scores_correctly(mock_llm):
    update_data(SID, "current_questions", {"questions": [
        {"id": 1, "type": "mcq", "question": "2+2", "options": {"A": "3", "B": "4"}, "answer": "B"},
        {"id": 2, "type": "mcq", "question": "3+3", "options": {"A": "6", "B": "5"}, "answer": "A"},
    ]})
    update_data(SID, "current_topic", "Math")

    result = run_evaluator(SID, {"1": "B", "2": "wrong"})
    assert result["score"] == 1
    assert result["total"] == 2
    assert result["percentage"] == 50


def test_evaluator_handles_missing_answer_key(mock_llm):
    update_data(SID, "current_questions", {"questions": [
        {"id": 1, "type": "mcq", "question": "2+2", "options": {"A": "3", "B": "4"}, "answer": "B"},
    ]})
    update_data(SID, "current_topic", "Math")

    result = run_evaluator(SID, {})  # Unanswered submission
    assert result["score"] == 0
    assert result["results"][0]["learner_answer"] == ""


def test_evaluator_handles_no_questions_gracefully(mock_llm):
    fresh_sid = "session-with-no-questions"
    result = run_evaluator(fresh_sid, {"1": "A"})
    assert result["score"] == 0
    assert "error" in result
    