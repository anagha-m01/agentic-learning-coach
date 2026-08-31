# 🧠 Agentic Learning Coach

An AI-powered full-stack web app that acts as your personal tutor. You tell it what you want to learn, your skill level, and how many days you have — it creates a personalised study plan, quizzes you daily, gives feedback, and delivers a final report.

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI |
| Frontend | React (Vite) |
| AI / LLM | Groq API (Llama 3.1) |
| Data Storage | JSON file (`learner_data.json`) |

---

## 📁 Project Structure

```
agentic-learning-coach/
├── backend/
│   ├── agents/
│   │   ├── skill_analyzer.py      # Analyses your skill level
│   │   ├── planner_agent.py       # Creates day-by-day study plan
│   │   ├── question_agent.py      # Generates 6 MCQs per day
│   │   ├── evaluator_agent.py     # Marks your answers
│   │   └── feedback_agent.py      # Decides pass / retry / revise
│   ├── utils/
│   │   ├── llm_client.py          # Talks to Groq AI API
│   │   └── json_store.py          # Reads/writes learner_data.json
│   ├── data/
│   │   └── learner_data.json      # Stores all session progress
│   └── main.py                    # FastAPI server
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── IntakeForm.jsx     # First form (topic, level, days)
│   │   │   ├── StudyPlan.jsx      # Displays the study plan
│   │   │   ├── Questions.jsx      # Shows daily MCQs
│   │   │   ├── Evaluation.jsx     # Shows results & explanations
│   │   │   └── Feedback.jsx       # Shows feedback & next step
│   │   ├── api.js                 # Connects frontend to backend
│   │   ├── App.jsx                # Main controller / stage manager
│   │   └── main.jsx               # React entry point
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.9+
- Node.js 18+
- A [Groq API key](https://console.groq.com)

---

### 1. Clone the repo

```bash
git clone https://github.com/your-username/agentic-learning-coach.git
cd agentic-learning-coach
```

### 2. Backend Setup

```bash
cd backend
pip install -r ../requirements.txt
```

Create a `.env` file inside the `backend/` folder:

```env
GROQ_API_KEY=your_groq_api_key_here
```

Start the backend server:

```bash
uvicorn main:app --reload
```

Backend runs at: `http://localhost:8000`

---

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

## 🚀 How It Works

1. **Fill the intake form** — enter topic, skill level, goal, and number of days
2. **Skill Analyzer** — AI figures out your weak areas and starting point
3. **Planner Agent** — generates a day-by-day study plan
4. **Question Agent** — creates 6 MCQs for today's topic
5. **Evaluator Agent** — marks your answers (pure Python, no AI)
6. **Feedback Agent** — decides: move on / retry / revise
7. **Final Day** — Practice Test covering all topics → final report with grade

---

## 🔑 Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key (get it from console.groq.com) |

> ⚠️ Never commit your `.env` file. It is already listed in `.gitignore`.

---

## 📌 Notes

- `learner_data.json` is auto-created on first run and stores session state
- Click **Start Over** in the app to reset all progress
- The last day of any plan is always a **Practice Test**