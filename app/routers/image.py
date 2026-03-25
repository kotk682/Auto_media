import logging

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from app.services.image import generate_images_batch, DEFAULT_MODEL
from app.core.api_keys import image_config_dep, get_art_style, inject_art_style, llm_config_dep
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.story_context import build_generation_payload
from app.services.story_context_service import prepare_story_context

router = APIRouter(prefix="/api/v1/image", tags=["image"])
logger = logging.getLogger(__name__)


class ImageRequest(BaseModel):
    shots: List[dict]
    model: Optional[str] = DEFAULT_MODEL
    story_id: Optional[str] = None


class ImageResult(BaseModel):
    shot_id: str
    image_url: str
    last_frame_url: Optional[str] = None


def _build_basic_payload(shot: dict, art_style: str) -> dict:
    image_prompt = (
        str(shot.get("image_prompt", "")).strip()
        or str(shot.get("visual_prompt", "")).strip()
        or str(shot.get("final_video_prompt", "")).strip()
    )
    if not image_prompt:
        raise ValueError(f"shot {shot.get('shot_id', '?')} 缺少 image_prompt/final_video_prompt")

    payload = {
        "shot_id": str(shot.get("shot_id", "")),
        "image_prompt": inject_art_style(image_prompt, art_style),
    }
    last_frame_prompt = str(shot.get("last_frame_prompt", "")).strip()
    if last_frame_prompt:
        payload["last_frame_prompt"] = inject_art_style(last_frame_prompt, art_style)
    return payload


@router.post("/{project_id}/generate", response_model=List[ImageResult])
async def generate_images(
    project_id: str,
    request: Request,
    body: ImageRequest,
    image_config: dict = Depends(image_config_dep),
    llm: dict = Depends(llm_config_dep),
    db: AsyncSession = Depends(get_db),
):
    art_style = get_art_style(request)
    try:
        story_context = None
        if body.story_id:
            _, story_context = await prepare_story_context(
                db,
                body.story_id,
                provider=llm["provider"],
                model=llm["model"],
                api_key=llm["api_key"],
                base_url=llm["base_url"],
            )
        payloads = [build_generation_payload(shot, story_context, art_style=art_style) for shot in body.shots]
        results = await generate_images_batch(
            payloads,
            model=body.model or DEFAULT_MODEL,
            art_style=art_style,
            **image_config,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Enhanced image generation failed for project=%s story_id=%s", project_id, body.story_id)
        if body.story_id:
            try:
                fallback_results = await generate_images_batch(
                    [_build_basic_payload(shot, art_style) for shot in body.shots],
                    model=body.model or DEFAULT_MODEL,
                    art_style=art_style,
                    **image_config,
                )
                return fallback_results
            except HTTPException:
                raise
            except Exception:
                logger.exception("Fallback image generation also failed for project=%s story_id=%s", project_id, body.story_id)
        detail = str(e).strip() or repr(e) or e.__class__.__name__
        raise HTTPException(status_code=500, detail=f"图片生成失败: {detail}") from e
    return results
