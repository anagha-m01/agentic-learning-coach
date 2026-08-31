from fastapi import APIRouter

from app.agents.skill_analyzer import run_skill_analyzer
from app.agents.planner_agent import run_planner
from app.agents.question_agent import run_question_generator
from app.agents.evaluator_agent import run_evaluator
from app.agents.feedback_agent import run_feedback_agent

from app.schemas.learning import (
    IntakeRequest,
    EvaluateRequest,
    QuestionRequest,
)

from app.storage.json_store import (
    get_value,
    save_data,
    update_data,
)


router = APIRouter()


@router.post("/analyze")
def analyze(req: IntakeRequest):
    skill = run_skill_analyzer(
        req.topic,
        req.level,
        req.goal,
    )

    plan = run_planner(req.days)

    day1_topic = skill.get(
        "starting_topic",
        req.topic,
    )

    if plan and plan.get("plan"):
        day1_topic = plan["plan"][0]["topic"]

    update_data("current_day", 0)
    update_data("total_days", req.days)
    update_data("current_topic", day1_topic)

    skill["starting_topic"] = day1_topic

    return {
        "skill": skill,
        "plan": plan,
    }


@router.post("/questions")
def questions(req: QuestionRequest):
    topic = get_value("current_topic")

    if not topic:
        skill_analysis = get_value("skill_analysis") or {}
        topic = req.topic or skill_analysis.get("starting_topic")

    return run_question_generator(topic)


@router.post("/evaluate")
def evaluate(req: EvaluateRequest):
    return run_evaluator(req.answers)


@router.post("/feedback")
def feedback():
    return run_feedback_agent()


@router.post("/reset")
def reset():
    save_data({})
    return {"status": "reset"}


@router.get("/state")
def state():
    return {
        "skill": get_value("skill_analysis"),
        "plan": get_value("study_plan"),
        "current": get_value("current_topic"),
        "day": get_value("current_day"),
        "total": get_value("total_days"),
        "questions": get_value("current_questions"),
        "eval": get_value("evaluation"),
        "feedback": get_value("feedback"),
    }