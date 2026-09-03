import os
import sys
import tempfile

# Initialize test environment variables before imports
os.environ.setdefault("GROQ_API_KEY", "test-dummy-key")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("RATE_LIMIT_DEFAULT", "1000/minute")
os.environ.setdefault("RATE_LIMIT_LLM", "1000/minute")  # Disable rate limits in tests

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Isolate test data directory per test."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Patch store data path for test isolation
    import app.storage.json_store as store
    monkeypatch.setattr(store, "DATA_FILE", os.path.join(str(tmp_path), "learner_data.json"))
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def mock_llm(monkeypatch):
    """Mock call_llm across agent modules."""
    import json as _json

    calls = {"count": 0, "prompts": []}

    def _fake_call_llm(system_prompt, user_message, model=None):
        calls["count"] += 1
        calls["prompts"].append((system_prompt, user_message))
        return calls.get("next_response") or _default_response(system_prompt, user_message)

    def _default_response(system_prompt, user_message):
        if "Skill Analyzer" in system_prompt:
            # Echo requested topic for session isolation testing
            topic = "Python"
            for line in user_message.splitlines():
                if line.startswith("Topic:"):
                    topic = line.split("Topic:", 1)[1].strip()
                    break
            return _json.dumps({
                "topic": topic, "skill_level": "beginner",
                "weaknesses": ["loops"], "starting_topic": "Variables",
                "goal": "learn basics"
            })
        if "Planner" in system_prompt or "day-by-day" in system_prompt:
            return _json.dumps({"plan": [
                {"day": i + 1, "topic": f"Day {i + 1} topic"} for i in range(5)
            ]})
        if "Question" in system_prompt or "MCQ" in system_prompt:
            return _json.dumps({"questions": [
                {"id": 1, "type": "mcq", "question": "2+2=?",
                 "options": {"A": "3", "B": "4", "C": "5", "D": "6"}, "answer": "B"}
            ]})
        if "Evaluator" in system_prompt:
            return _json.dumps({
                "results": [{"question_id": 1, "explanation": "Because math."}],
                "overall_feedback": "Good job!"
            })
        if "final performance summary" in system_prompt:
            return _json.dumps({
                "summary": "Solid effort overall.",
                "strengths": ["Good grasp of basics"],
                "improvements": ["Practice more edge cases"],
                "next_steps": "Review the topics you missed."
            })
        if "Feedback and Decision Agent" in system_prompt:
            return _json.dumps({
                "decision": "next_topic",
                "feedback": "Nice work, moving on!",
                "reason": "Scored above the threshold."
            })
        return _json.dumps({"feedback": "Keep going!"})

    for mod_name in [
        "app.agents.skill_analyzer",
        "app.agents.planner_agent",
        "app.agents.question_agent",
        "app.agents.evaluator_agent",
        "app.agents.feedback_agent",
    ]:
        import importlib
        mod = importlib.import_module(mod_name)
        monkeypatch.setattr(mod, "call_llm", _fake_call_llm)

    return calls
