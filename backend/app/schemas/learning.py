from typing import Optional

from pydantic import BaseModel, Field


class IntakeRequest(BaseModel):
    topic: str
    level: str
    goal: str
    days: int = Field(gt=1, le=30, description="Total days including the final practice test day")


class EvaluateRequest(BaseModel):
    answers: dict


class QuestionRequest(BaseModel):
    topic: Optional[str] = None