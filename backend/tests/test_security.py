"""Security tests: rate limiting, CORS, cookie flags, and error handling."""
import importlib
import os

import pytest
from fastapi.testclient import TestClient


DEFAULT_TEST_ENV = {
    "ENVIRONMENT": "development",
    "RATE_LIMIT_DEFAULT": "1000/minute",
    "RATE_LIMIT_LLM": "1000/minute",
    "FRONTEND_ORIGINS": "",
}


def _reload_app_modules():
    import app.core.config as config_module
    importlib.reload(config_module)
    import app.core.session as session_module
    importlib.reload(session_module)
    import app.api.routes as routes_module
    importlib.reload(routes_module)
    import app.main as main_module
    importlib.reload(main_module)
    return main_module


@pytest.fixture
def rebuilt_app(monkeypatch, isolated_data_dir):
    """Factory fixture providing a TestClient with custom environment settings."""

    def _build(**env_overrides):
        for key, value in env_overrides.items():
            monkeypatch.setenv(key, value)
        main_module = _reload_app_modules()
        return TestClient(main_module.app)

    yield _build

    for key, value in DEFAULT_TEST_ENV.items():
        os.environ[key] = value
    _reload_app_modules()


def test_rate_limit_returns_429_after_threshold(rebuilt_app, mock_llm):
    client = rebuilt_app(RATE_LIMIT_LLM="2/minute", RATE_LIMIT_DEFAULT="2/minute")

    # Initialize session cookie before rate-limited requests
    client.get("/state")

    payload = {"topic": "Python", "level": "beginner", "goal": "x", "days": 5}
    r1 = client.post("/analyze", json=payload)
    r2 = client.post("/analyze", json=payload)
    r3 = client.post("/analyze", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_cors_rejects_unlisted_origin(client):
    resp = client.get("/health", headers={"Origin": "https://evil-attacker.example"})
    acao = resp.headers.get("access-control-allow-origin")
    assert acao != "https://evil-attacker.example"


def test_cors_preflight_allows_configured_origin(rebuilt_app):
    client = rebuilt_app(FRONTEND_ORIGINS="https://my-app.vercel.app")
    resp = client.options(
        "/analyze",
        headers={
            "Origin": "https://my-app.vercel.app",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "https://my-app.vercel.app"


def test_session_cookie_is_httponly(client, mock_llm):
    resp = client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 5
    })
    set_cookie_header = resp.headers.get("set-cookie", "")
    assert "httponly" in set_cookie_header.lower()


def test_production_cookie_uses_secure_and_samesite_none(rebuilt_app, mock_llm):
    client = rebuilt_app(ENVIRONMENT="production", FRONTEND_ORIGINS="https://my-app.vercel.app")
    resp = client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 5
    })
    set_cookie_header = resp.headers.get("set-cookie", "").lower()
    assert "secure" in set_cookie_header
    assert "samesite=none" in set_cookie_header


def test_unhandled_exception_does_not_leak_stack_trace(monkeypatch, mock_llm):
    def boom(*args, **kwargs):
        raise RuntimeError("some internal secret detail")

    import app.agents.skill_analyzer as skill_mod
    monkeypatch.setattr(skill_mod, "call_llm", boom)

    # Verify 500 response without internal exception leakage
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post("/analyze", json={
        "topic": "Python", "level": "beginner", "goal": "x", "days": 5
    })
    assert resp.status_code == 500
    body = resp.json()
    assert "some internal secret detail" not in str(body)
    assert body == {"error": "Internal server error. Please try again."}


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    