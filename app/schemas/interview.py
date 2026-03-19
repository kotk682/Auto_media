from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class InterviewStage(str, Enum):
    TOPIC = "topic"
    AUDIENCE = "audience"
    TONE = "tone"
    DURATION = "duration"
    COMPLETE = "complete"


class InterviewStateResponse(BaseModel):
    project_id: str
    stage: InterviewStage
    question: str
    hint: Optional[str] = None
    progress: int = Field(..., ge=0, le=100, description="Interview completion %")
    is_complete: bool = False


class ChatRequest(BaseModel):
    answer: str


class ProjectInitRequest(BaseModel):
    seed_idea: str


class ProjectInitResponse(BaseModel):
    project_id: str
    message: str
    first_question: str
