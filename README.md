# Agentic Learning Coach

An AI-powered learning coach that builds you a personalized, day-by-day study plan for any topic, then quizzes you and adapts as you go — powered by a pipeline of cooperating LLM agents rather than a single prompt.

## Overview

Tell it what you want to learn, your current skill level, your goal, and how many days you have. It analyzes your starting point, generates a structured multi-day curriculum that progresses from fundamentals to advanced material, quizzes you on each topic, evaluates your answers, and gives targeted feedback — all backed by Groq-hosted LLMs.

## How it works

The backend runs a small pipeline of specialized agents instead of one general-purpose prompt:

| Agent | Responsibility |
|---|---|
| `skill_analyzer` | Assesses stated skill level and goal, identifies likely weak spots and a sensible starting topic |
| `planner_agent` | Builds a day-by-day curriculum with strict difficulty progression (basics → advanced), ending in a practice-test day |
| `question_agent` | Generates topic-specific quiz questions for the current day |
| `evaluator_agent` | Scores submitted answers in Python (not left to the LLM to self-grade) |
| `feedback_agent` | Produces personalized feedback based on evaluation results |

Each agent validates and retries on malformed LLM output before falling back to a safe default, so a single bad generation doesn't crash the flow.

## Tech stack

**Backend:** FastAPI, Groq API (LLM inference), Pydantic, JSON-file storage
**Frontend:** React, Vite, Axios, Tailwind-style CSS

## Features

- Personalized day-by-day study plans with enforced difficulty progression
- Adaptive quiz generation per topic
- Objective, code-based answer evaluation (not just LLM opinion)
- Automatic retry/repair when the LLM returns malformed JSON
- Configurable plan length (2–30 days)

## Project structure

```
backend/
  app/
    agents/        # the 5 LLM agents described above
    api/            # FastAPI routes
    core/           # Groq client wrapper
    schemas/        # Pydantic request/response models
    storage/        # simple JSON-file session store
  requirements.txt
frontend/
  src/
    components/     # IntakeForm, StudyPlan, Questions, Evaluation, Feedback
    api.js          # backend API client
```

## Installation

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
Edit `.env` and add your [Groq API key](https://console.groq.com/keys):
```
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-120b
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

## Usage

1. Enter what you want to learn, your skill level, your goal, and pick a study duration.
2. Click **Start Learning** — the coach analyzes your input and generates a full study plan.
3. Work through each day's quiz questions.
4. Submit your answers to get scored, objective feedback.
5. Progress automatically advances to the next day's topic.

## Deployment

This is a two-part deploy: the FastAPI backend and the Vite/React frontend go to separate hosts.

**Backend (Render, free tier):**
1. Push this repo to GitHub (done).
2. On [Render](https://render.com), create a new **Web Service** pointing at this repo, root directory `backend`.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables in Render's dashboard: `GROQ_API_KEY`, `GROQ_MODEL`, and once you know your frontend's URL, `FRONTEND_ORIGINS` (e.g. `https://your-app.vercel.app`).

**Frontend (Vercel or Netlify, free tier):**
1. Import this repo, root directory `frontend`.
2. Framework preset: Vite.
3. Add environment variable `VITE_API_BASE_URL` set to your deployed Render backend URL (e.g. `https://agentic-learning-coach.onrender.com`).
4. Deploy.

> **Known limitation:** session state is stored in a local JSON file (`backend/data/learner_data.json`), not a database. On most free-tier hosts the filesystem is ephemeral, so state can reset on redeploy or after periods of inactivity, and concurrent users currently share the same session state. Fine for a personal demo; a proper deploy would move this to a real database keyed by session/user ID.

## License

MIT — see [LICENSE](LICENSE).