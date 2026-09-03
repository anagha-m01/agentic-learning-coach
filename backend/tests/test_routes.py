"""Integration tests for API routes."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_sets_session_cookie(client, mock_llm):
    resp = client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "learn basics", "days": 5
    })
    assert resp.status_code == 200
    assert "alc_session" in resp.cookies
    body = resp.json()
    assert body["skill"]["topic"] == "Python"
    assert body["plan"]["total_days"] == 5


def test_full_happy_path_flow(client, mock_llm):
    # 1. Analyze
    r1 = client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "learn basics", "days": 5
    })
    assert r1.status_code == 200

    # 2. Questions
    r2 = client.post("/questions", json={})
    assert r2.status_code == 200
    questions = r2.json()["questions"]
    assert len(questions) >= 1

    # 3. Evaluate
    answers = {str(q["id"]): q["answer"] for q in questions}  # Correct answers
    r3 = client.post("/evaluate", json={"answers": answers})
    assert r3.status_code == 200
    assert r3.json()["score"] == r3.json()["total"]

    # 4. Feedback
    r4 = client.post("/feedback")
    assert r4.status_code == 200
    assert r4.json()["decision"] in {"next_topic", "repeat_topic", "revise_topic", "complete"}

    # 5. Verify state
    r5 = client.get("/state")
    assert r5.status_code == 200
    state = r5.json()
    assert state["skill"]["topic"] == "Python"
    assert state["eval"]["score"] == state["eval"]["total"]


def test_reset_clears_session(client, mock_llm):
    client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "learn basics", "days": 5
    })
    r = client.post("/reset")
    assert r.status_code == 200
    assert r.json() == {"status": "reset"}

    state = client.get("/state").json()
    # Verify cleared session state
    assert state["skill"] is None


def test_questions_without_prior_analyze_returns_graceful_error(client, mock_llm):
    resp = client.post("/questions", json={})
    assert resp.status_code == 200
    assert "error" in resp.json()


# Route validation tests

def test_analyze_rejects_too_few_days(client):
    resp = client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 1
    })
    assert resp.status_code == 422


def test_analyze_rejects_too_many_days(client):
    resp = client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 31
    })
    assert resp.status_code == 422


def test_analyze_rejects_empty_topic(client):
    resp = client.post("/analyze", json={
        "topic": "   ", "level": "beginner", "goal": "x", "days": 5
    })
    assert resp.status_code == 422


def test_analyze_rejects_oversized_topic(client):
    resp = client.post("/analyze", json={
        "topic": "x" * 500, "level": "beginner", "goal": "x", "days": 5
    })
    assert resp.status_code == 422


def test_analyze_rejects_invalid_level(client):
    resp = client.post("/analyze", json={
        "topic": "Python", "level": "godlike", "goal": "x", "days": 5
    })
    assert resp.status_code == 422


def test_evaluate_rejects_oversized_answers_payload(client, mock_llm):
    client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 5
    })
    huge_answers = {str(i): "A" for i in range(200)}
    resp = client.post("/evaluate", json={"answers": huge_answers})
    assert resp.status_code == 422


def test_evaluate_rejects_oversized_answer_value(client, mock_llm):
    resp = client.post("/evaluate", json={"answers": {"1": "A" * 50}})
    assert resp.status_code == 422


def test_evaluate_handles_malformed_answer_types_gracefully(client, mock_llm):
    # Verify handling of empty answers payload
    client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 5
    })
    client.post("/questions", json={})
    resp = client.post("/evaluate", json={"answers": {}})
    assert resp.status_code == 200
    assert resp.json()["score"] == 0
    