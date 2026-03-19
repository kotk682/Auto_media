from pydantic import BaseModel
from typing import Optional
from enum import Enum


class PipelineStatus(str, Enum):
    PENDING = "pending"
    STORYBOARD = "storyboard"
    GENERATING_ASSETS = "generating_assets"
    RENDERING_VIDEO = "rendering_video"
    STITCHING = "stitching"
    COMPLETE = "complete"
    FAILED = "failed"


class PipelineStatusResponse(BaseModel):
    project_id: str
    status: PipelineStatus
    progress: int
    current_step: str
    error: Optional[str] = None
