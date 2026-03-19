from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.tts import generate_tts_batch, VOICES, DEFAULT_VOICE

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


class TTSRequest(BaseModel):
    shots: List[dict]
    voice: Optional[str] = DEFAULT_VOICE


class TTSResult(BaseModel):
    shot_id: str
    audio_url: str
    duration_seconds: float


@router.get("/voices")
async def list_voices():
    return [{"id": k, "name": v} for k, v in VOICES.items()]


@router.post("/{project_id}/generate", response_model=List[TTSResult])
async def generate_audio(project_id: str, body: TTSRequest):
    voice = body.voice or DEFAULT_VOICE
    if voice not in VOICES:
        raise HTTPException(status_code=400, detail=f"Unknown voice: {voice}")
    try:
        results = await generate_tts_batch(body.shots, voice=voice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS 生成失败: {e}")
    return results
