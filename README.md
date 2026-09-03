# Agentic Learning Coach

An AI-powered learning coach that builds a personalized, day-by-day study plan for any topic, then quizzes you and adapts as you go — powered by a pipeline of cooperating LLM agents rather than a single prompt.

**Live demo:** _add your deployed link here after following [Deployment](#deployment) below_
**API docs:** _`<your-render-url>`/docs_

---

## Overview

Tell it what you want to learn, your current skill level, your goal, and how many days you have. It analyzes your starting point, generates a structured multi-day curriculum that progresses from fundamentals to advanced material, quizzes you on each topic, evaluates your answers, and gives targeted feedback — all backed by Groq-hosted LLMs.

No login required: each browser gets an isolated session via a secure cookie, so you can try it immediately.

## Architecture

```
┌─────────────┐      HTTPS + session cookie      ┌──────────────────┐
│   Frontend   │ ───────────────────────────────► │     Backend      │
│  React/Vite  │ ◄─────────────────────────────── │     FastAPI      │
│   (Vercel)   │                                   │     (Render)     │
└─────────────┘                                   └────────┬─────────┘
                                                             │
                                          ┌──────────────────┼──────────────────┐
                                          ▼                  ▼                  ▼
                                   skill_analyzer      planner_agent     question_agent
                                          │                                     │
                                          ▼                                     ▼
                                   evaluator_agent  ◄──────────────  feedback_agent
                                          │
                                          ▼
                                 session-scoped JSON store
                                  (keyed by session cookie)
```

The backend runs a small pipeline of specialized agents instead of one general-purpose prompt:

| Agent | Responsibility |
|---|---|
| `skill_analyzer` | Assesses stated skill level and goal, identifies likely weak spots and a sensible starting topic |
| `planner_agent` | Builds a day-by-day curriculum with strict difficulty progression (basics → advanced), ending in a practice-test day |
| `question_agent` | Generates topic-specific quiz questions for the current day |
| `evaluator_agent` | Scores submitted answers in Python (not left to the LLM to self-grade) |
| `feedback_agent` | Produces personalized feedback and decides next-topic / repeat / revise |

Each agent validates and retries on malformed LLM output before falling back to a safe default, so a single bad generation doesn't crash the flow.

## Tech stack

**Backend:** FastAPI, Groq API (LLM inference), Pydantic v2, slowapi (rate limiting), session-scoped JSON-file storage
**Frontend:** React 19, Vite, Axios
**Testing:** pytest + TestClient (backend), Vitest + React Testing Library (frontend)
**CI:** GitHub Actions (lint, test, build on every push/PR)

## Features

- Personalized day-by-day study plans with enforced difficulty progression
- Adaptive quiz generation per topic
- Objective, code-based answer evaluation (not just LLM opinion)
- Automatic retry/repair when the LLM returns malformed JSON
- Configurable plan length (2–30 days)
- Per-visitor session isolation via a secure httpOnly cookie — no login needed, and no risk of one visitor's study data leaking into another's

## Security & production readiness

This started as a personal project and has since been hardened for a public demo:

- **Session isolation** — every visitor gets a cryptographically random session ID (`secrets.token_urlsafe(32)`) in an httpOnly cookie. In production the cookie is `Secure; SameSite=None` (required since the Vercel frontend and Render backend are different domains); locally it's `SameSite=Lax` over plain http. Sessions auto-expire after 24h of inactivity.
- **Rate limiting** — LLM-calling endpoints are capped per session (`RATE_LIMIT_LLM`, default 10/minute) to prevent runaway API costs from a bot or an accidental infinite-loop client.
- **Input validation** — topic/goal length caps, control-character stripping, whitelisted skill levels, a bounded answer-map shape — all enforced by Pydantic validators before anything reaches an LLM prompt.
- **CORS** — explicit origin allowlist (no wildcard), restricted methods/headers, credentials only sent to allowed origins.
- **Error handling** — a catch-all exception handler returns a generic message; stack traces are logged server-side (structured JSON) and never sent to the client.
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` on every response.
- **Structured logging** — JSON logs to stdout (Render-friendly), with session IDs truncated before logging.
- **`.env` hygiene** — no secrets in git; `.env.example` documents every variable; `GROQ_API_KEY` is validated at startup so misconfiguration fails immediately and loudly instead of on the first request.

## Testing

```bash
# backend (38 tests: unit, integration, session-isolation, security/edge cases)
cd backend && pip install -r requirements-dev.txt && pytest -q

# frontend (12 tests: components + API client)
cd frontend && npm install && npm test
```

Both suites run automatically on every push via GitHub Actions (`.github/workflows/ci.yml`), including a full `npm run build` to catch build-breaking changes before merge.

## Project structure

```
backend/
  app/
    agents/         # the 5 LLM agents described above
    api/             # FastAPI routes (session cookie handling, rate limiting)
    core/            # config, logging, session, Groq client wrapper
    schemas/         # Pydantic request/response models with validation
    storage/         # session-scoped JSON-file store
  tests/             # pytest suite (unit / integration / security / session-isolation)
  requirements.txt
  requirements-dev.txt
frontend/
  src/
    components/      # IntakeForm, StudyPlan, Questions, Evaluation, Feedback
    components/__tests__/
    api.js           # backend API client (withCredentials for the session cookie)
.github/workflows/ci.yml
```

## Installation (local development)

### 1. Clone the repository
```bash
git clone git@github.com:anagha-m01/agentic-learning-coach.git
cd agentic-learning-coach
```

### 2. Backend setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
cp .env.example .env
```
Edit `.env` and add your [Groq API key](https://console.groq.com/keys) (everything else has sensible local defaults):
```
GROQ_API_KEY=your_key_here
```

Run it:
```bash
uvicorn app.main:app --reload
```
API is now live at `http://127.0.0.1:8000` — interactive docs at `http://127.0.0.1:8000/docs`.

### 3. Frontend setup
```bash
cd frontend
npm install
cp .env.example .env   # leave VITE_API_BASE_URL blank for local dev
npm run dev
```
App is now live at `http://localhost:5173`.

## Environment variables

**Backend (`backend/.env`)**

| Variable | Required | Default | Notes |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ | — | App fails to start without it |
| `GROQ_MODEL` | | `openai/gpt-oss-120b` | Any current Groq-supported model |
| `ENVIRONMENT` | | `development` | `production` enables `Secure`/`SameSite=None` cookies |
| `FRONTEND_ORIGINS` | production only | *(empty)* | Comma-separated; must exactly match your deployed frontend URL |
| `SESSION_COOKIE_NAME` | | `alc_session` | |
| `SESSION_TTL_HOURS` | | `24` | Idle sessions are pruned after this |
| `RATE_LIMIT_DEFAULT` / `RATE_LIMIT_LLM` | | `60/minute` / `10/minute` | Per-session request caps |
| `DATA_DIR` | | `data` | Where session JSON is written (ephemeral on Render's free tier) |
| `LOG_LEVEL` | | `INFO` | |

**Frontend (`frontend/.env`)**

| Variable | Required | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | production only | Your deployed Render backend URL |

## Usage

1. Enter what you want to learn, your skill level, your goal, and pick a study duration.
2. Click **Start Learning** — the coach analyzes your input and generates a full study plan.
3. Work through each day's quiz questions.
4. Submit your answers to get scored, objective feedback.
5. Progress automatically advances to the next day's topic.

## Deployment

This is a two-part deploy: the FastAPI backend and the Vite/React frontend go to separate hosts, plus the session cookie needs to be configured to work cross-domain.

**Backend (Render, free tier):**
1. Push this repo to GitHub.
2. On [Render](https://render.com), create a new **Web Service** pointing at this repo, root directory `backend`.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables in Render's dashboard: `GROQ_API_KEY`, `ENVIRONMENT=production`, and (once you know it) `FRONTEND_ORIGINS=https://your-app.vercel.app`. The rest have working defaults — see the table above.
6. Deploy, then confirm `https://<your-render-url>/health` returns `{"status": "ok"}`.

**Frontend (Vercel, free tier):**
1. Import this repo, root directory `frontend`.
2. Framework preset: Vite.
3. Add environment variable `VITE_API_BASE_URL` set to your deployed Render backend URL (e.g. `https://agentic-learning-coach.onrender.com`).
4. Deploy.
5. Go back to Render and set `FRONTEND_ORIGINS` to your new Vercel URL (exact match, no trailing slash), then redeploy the backend — CORS will reject the frontend until this matches.

**Why the cookie config matters:** the frontend and backend are on different domains, so the session cookie needs `SameSite=None; Secure` to be sent cross-site at all (that's what `ENVIRONMENT=production` turns on) — and both ends need HTTPS, which Render and Vercel provide by default. If the deployed app seems to "forget" your study plan between requests, check that `ENVIRONMENT=production` is set on Render and that `FRONTEND_ORIGINS` matches your Vercel URL exactly.

> **Known limitation:** session data is stored in a local JSON file, not a database. On Render's free tier the filesystem is ephemeral, so state can be lost on redeploy or after a period of inactivity (the instance spins down and back up). Each visitor's data is isolated from every other visitor's (see [Security](#security--production-readiness) above), but it isn't durable across redeploys. Fine for a demo; a production version would move this to a real database keyed by session ID.

## License

MIT — see [LICENSE](LICENSE).
