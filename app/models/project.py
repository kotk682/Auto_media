from sqlalchemy import Column, String, Text, Integer, Float, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.schemas.interview import InterviewStage
from app.schemas.pipeline import PipelineStatus


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    seed_idea = Column(Text, nullable=False)
    stage = Column(SAEnum(InterviewStage), default=InterviewStage.TOPIC)
    topic = Column(Text)
    audience = Column(Text)
    tone = Column(Text)
    duration = Column(Text)
    script = Column(Text)
    pipeline_status = Column(SAEnum(PipelineStatus), default=PipelineStatus.PENDING)
    pipeline_progress = Column(Integer, default=0)
