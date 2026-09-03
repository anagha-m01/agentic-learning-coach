"""Tests verifying isolation between distinct browser sessions."""
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.session import generate_session_id, _looks_valid


def test_session_ids_are_unique_and_high_entropy():
    ids = {generate_session_id() for _ in range(1000)}
    assert len(ids) == 1000  # Unique IDs
    assert all(len(i) >= 40 for i in ids)  # Sufficient length


def test_malformed_cookie_value_is_rejected():
    assert _looks_valid("a" * 43) is True
    assert _looks_valid("../../etc/passwd") is False
    assert _looks_valid("short") is False
    assert _looks_valid("has spaces in it padded to be long enough") is False


def test_two_browsers_get_different_session_cookies(client, mock_llm):
    client_a = TestClient(client.app)
    client_b = TestClient(client.app)

    r1 = client_a.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 5
    })
    r2 = client_b.post("/analyze", json={
        "topic": "Machine Learning", "level": "advanced", "goal": "y", "days": 5
    })

    sid_a = r1.cookies.get(settings.session_cookie_name)
    sid_b = r2.cookies.get(settings.session_cookie_name)
    assert sid_a is not None and sid_b is not None
    assert sid_a != sid_b


def test_two_sessions_do_not_see_each_others_state(client, mock_llm):
    client_a = TestClient(client.app)
    client_b = TestClient(client.app)

    client_a.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 5
    })
    client_b.post("/analyze", json={
        "topic": "Machine Learning", "level": "advanced", "goal": "y", "days": 5
    })

    state_a = client_a.get("/state").json()
    state_b = client_b.get("/state").json()

    assert state_a["skill"]["topic"] == "Python"
    assert state_b["skill"]["topic"] == "Machine Learning"
    assert state_a["skill"]["topic"] != state_b["skill"]["topic"]


def test_answering_questions_in_one_session_does_not_affect_the_other(client, mock_llm):
    client_a = TestClient(client.app)
    client_b = TestClient(client.app)

    client_a.post("/analyze", json={"topic": "Python", "level": "beginner", "goal": "x", "days": 5})
    client_b.post("/analyze", json={"topic": "SQL", "level": "beginner", "goal": "y", "days": 5})

    client_a.post("/questions", json={})
    client_b.post("/questions", json={})

    client_a.post("/evaluate", json={"answers": {"1": "B"}})  # Mock correct answer

    state_a = client_a.get("/state").json()
    state_b = client_b.get("/state").json()

    assert state_a["eval"] is not None
    assert state_b["eval"] is None  # Session B unaffected


def test_reset_only_clears_the_calling_sessions_data(client, mock_llm):
    client_a = TestClient(client.app)
    client_b = TestClient(client.app)

    client_a.post("/analyze", json={"topic": "Python", "level": "beginner", "goal": "x", "days": 5})
    client_b.post("/analyze", json={"topic": "SQL", "level": "beginner", "goal": "y", "days": 5})

    client_a.post("/reset")

    state_a = client_a.get("/state").json()
    state_b = client_b.get("/state").json()

    assert state_a["skill"] is None  # Session A reset
    assert state_b["skill"]["topic"] == "SQL"  # Session B preserved


def test_request_with_no_cookie_at_all_gets_a_fresh_session(client, mock_llm):
    # Handle request without existing cookie
    resp = client.get("/state")
    assert resp.status_code == 200
    assert resp.json()["skill"] is None
    assert settings.session_cookie_name in resp.cookies


def test_tampered_cookie_value_does_not_leak_another_sessions_data(client, mock_llm):
    client_a = TestClient(client.app)
    client_a.post("/analyze", json={"topic": "Python", "level": "beginner", "goal": "x", "days": 5})
    real_sid = client_a.cookies.get(settings.session_cookie_name)
    assert real_sid

    # Reject invalid or partial session IDs
    guessed = real_sid[:10]
    client_c = TestClient(client.app)
    client_c.cookies.set(settings.session_cookie_name, guessed)
    state_c = client_c.get("/state").json()
    assert state_c["skill"] is None
    