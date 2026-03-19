from pydantic import BaseModel, Field
from typing import List, Optional


class Shot(BaseModel):
    shot_id: str = Field(description="Unique ID, e.g. scene1_shot1")
    visual_description_zh: str = Field(description="简短的中文画面描述，供团队审阅用。")
    visual_prompt: str = Field(description="Highly detailed English prompt for image generation, includes character, environment, lighting, camera angle, and style tags.")
    camera_motion: str = Field(description="Simple English instruction for video generation, e.g. 'Pan right', 'Zoom in slowly', 'Static'.")
    dialogue: Optional[str] = Field(default=None, description="Exact Chinese text for TTS. None if no dialogue.")
    estimated_duration: int = Field(default=4, description="Estimated duration in seconds (3-5).")


class Storyboard(BaseModel):
    shots: List[Shot]
