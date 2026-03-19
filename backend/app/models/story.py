from pydantic import BaseModel
from typing import List, Optional


class AnalyzeIdeaRequest(BaseModel):
    idea: str
    genre: str
    tone: str


class SuggestionGroup(BaseModel):
    label: str
    options: List[str]


class AnalyzeIdeaResponse(BaseModel):
    story_id: str
    analysis: str
    suggestions: List[SuggestionGroup]
    placeholder: str


class GenerateOutlineRequest(BaseModel):
    story_id: str
    selected_setting: str


class Character(BaseModel):
    name: str
    role: str
    description: str


class OutlineScene(BaseModel):
    episode: int
    title: str
    summary: str


class Relationship(BaseModel):
    source: str
    target: str
    label: str


class GenerateOutlineResponse(BaseModel):
    story_id: str
    meta: dict
    characters: List[Character]
    relationships: List[Relationship]
    outline: List[OutlineScene]


class ChatRequest(BaseModel):
    story_id: str
    message: str


class GenerateScriptRequest(BaseModel):
    story_id: str


class RefineRequest(BaseModel):
    story_id: str
    change_type: str  # "character" | "episode"
    change_summary: str  # 描述改了什么


class RefineResponse(BaseModel):
    relationships: Optional[List[Relationship]]
    outline: Optional[List[OutlineScene]]
    meta_theme: Optional[str]


class AudioLine(BaseModel):
    character: str
    line: str


class ScriptScene(BaseModel):
    scene_number: int
    environment: str
    visual: str
    audio: List[AudioLine]


class SceneScript(BaseModel):
    episode: int
    title: str
    scenes: List[ScriptScene]
