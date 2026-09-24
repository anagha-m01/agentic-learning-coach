from fastapi import APIRouter, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.agents.skill_analyzer import run_skill_analyzer
from app.agents.planner_agent import run_planner
from app.agents.question_agent import run_question_generator
from app.agents.evaluator_agent import run_evaluator
from app.agents.feedback_agent import run_feedback_agent

from app.core.adaptive import DAY_TYPE_LEARNING
from app.core.config import settings
from app.core.logging_config import get_logger, mask_session
from app.core.session import (
    clear_session_cookie,
    get_or_create_session_id,
)

from app.schemas.learning import (
    IntakeRequest,
    EvaluateRequest,
    QuestionRequest,
)

from app.storage.json_store import (
    get_value,
    save_session,
    update_data,
)

logger = get_logger(__name__)
router = APIRouter()

# Rate limit by session cookie or client IP
def _rate_limit_key(request: Request) -> str:
    session_id = request.cookies.get(settings.session_cookie_name)
    return session_id or get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key, default_limits=[settings.rate_limit_default])


@router.get("/health")
def health():
    """Health check probe."""
    return {"status": "ok"}


@router.post("/analyze")
@limiter.limit(settings.rate_limit_llm)
def analyze(req: IntakeRequest, request: Request, response: Response):
    session_id = get_or_create_session_id(request, response)

    skill = run_skill_analyzer(
        session_id,
        req.topic,
        req.level,
        req.goal,
    )

    # The learner's own selected level is the starting difficulty, stored
    # separately from skill_analysis["skill_level"] so later agents adapt a
    # value that is never silently overwritten by an LLM's own assessment.
    update_data(session_id, "difficulty", req.level)

    plan = run_planner(session_id, req.days)

    day1_topic = skill.get(
        "starting_topic",
        req.topic,
    )
    day1_type = DAY_TYPE_LEARNING

    if plan and plan.get("plan"):
        day1_topic = plan["plan"][0]["topic"]
        day1_type = plan["plan"][0].get("day_type", DAY_TYPE_LEARNING)

    update_data(session_id, "current_day", 0)
    update_data(session_id, "total_days", req.days)
    update_data(session_id, "current_topic", day1_topic)
    update_data(session_id, "current_day_type", day1_type)

    skill["starting_topic"] = day1_topic

    logger.info("analyze completed", extra={
        "extra_fields": {"session": mask_session(session_id), "days": req.days}
    })

    return {
        "skill": skill,
        "plan": plan,
    }


@router.post("/questions")
@limiter.limit(settings.rate_limit_llm)
def questions(req: QuestionRequest, request: Request, response: Response):
    session_id = get_or_create_session_id(request, response)

    # The server-stored topic is always authoritative once a session has
    # started -- the client-supplied topic is only a fallback for the very
    # first request before /analyze has run. If a client ever sends a
    # different topic than the server holds (a stale tab, a desynced
    # frontend state), we trust the server and just note the mismatch.
    topic = get_value(session_id, "current_topic")

    if not topic:
        skill_analysis = get_value(session_id, "skill_analysis") or {}
        topic = req.topic or skill_analysis.get("starting_topic")

    if not topic:
        return {"error": "No topic set for this session yet. Call /analyze first."}

    if req.topic and topic != req.topic:
        logger.info("questions: client topic differs from server topic, using server topic", extra={
            "extra_fields": {"session": mask_session(session_id)}
        })

    return run_question_generator(session_id, topic)


@router.post("/evaluate")
@limiter.limit(settings.rate_limit_llm)
def evaluate(req: EvaluateRequest, request: Request, response: Response):
    session_id = get_or_create_session_id(request, response)
    return run_evaluator(session_id, req.answers)


@router.post("/feedback")
@limiter.limit(settings.rate_limit_llm)
def feedback(request: Request, response: Response):
    session_id = get_or_create_session_id(request, response)
    return run_feedback_agent(session_id)


@router.post("/reset")
def reset(request: Request, response: Response):
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        save_session(session_id, {})
        clear_session_cookie(response)
    return {"status": "reset"}


@router.get("/state")
def state(request: Request, response: Response):
    session_id = get_or_create_session_id(request, response)
    return {
        "skill": get_value(session_id, "skill_analysis"),
        "plan": get_value(session_id, "study_plan"),
        "current": get_value(session_id, "current_topic"),
        "day": get_value(session_id, "current_day"),
        "day_type": get_value(session_id, "current_day_type"),
        "total": get_value(session_id, "total_days"),
        "questions": get_value(session_id, "current_questions"),
        "eval": get_value(session_id, "evaluation"),
        "feedback": get_value(session_id, "feedback"),
        "difficulty": get_value(session_id, "difficulty"),
        "weak_concepts": get_value(session_id, "weak_concepts"),
        "strong_concepts": get_value(session_id, "strong_concepts"),
    }
    