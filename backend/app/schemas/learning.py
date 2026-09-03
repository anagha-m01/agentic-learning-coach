import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Input sanitization and bounds
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAX_TOPIC_LEN = 200
_MAX_GOAL_LEN = 500
_ALLOWED_LEVELS = {"beginner", "intermediate", "advanced"}


def _sanitize_text(value: str, max_len: int) -> str:
    value = _CONTROL_CHARS.sub("", value).strip()
    if not value:
        raise ValueError("must not be empty")
    if len(value) > max_len:
        raise ValueError(f"must be {max_len} characters or fewer")
    return value


class IntakeRequest(BaseModel):
    topic: str
    level: str
    goal: str
    days: int = Field(gt=1, le=30, description="Total days including the final practice test day")

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        return _sanitize_text(v, _MAX_TOPIC_LEN)

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str) -> str:
        return _sanitize_text(v, _MAX_GOAL_LEN)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in _ALLOWED_LEVELS:
            raise ValueError(f"level must be one of {sorted(_ALLOWED_LEVELS)}")
        return v


class EvaluateRequest(BaseModel):
    # Bounded answer map to restrict payload size
    answers: dict[str, str] = Field(default_factory=dict)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, v: dict) -> dict:
        if len(v) > 100:
            raise ValueError("too many answers in a single submission")
        cleaned = {}
        for key, val in v.items():
            if len(str(key)) > 20 or len(str(val)) > 20:
                raise ValueError("answer key/value too long")
            cleaned[str(key)] = str(val)
        return cleaned


class QuestionRequest(BaseModel):
    topic: Optional[str] = None

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _sanitize_text(v, _MAX_TOPIC_LEN)
    