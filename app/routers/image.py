from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from app.services.image import generate_images_batch, DEFAULT_MODEL
from app.core.api_keys import image_config_dep, get_art_style

router = APIRouter(prefix="/api/v1/image", tags=["image"])


class ImageRequest(BaseModel):
    shots: List[dict]
    model: Optional[str] = DEFAULT_MODEL


class ImageResult(BaseModel):
    shot_id: str
    image_url: str
    last_frame_url: Optional[str] = None


@router.post("/{project_id}/generate", response_model=List[ImageResult])
async def generate_images(project_id: str, request: Request, body: ImageRequest, image_config: dict = Depends(image_config_dep)):
    art_style = get_art_style(request)
    try:
        results = await generate_images_batch(
            body.shots,
            model=body.model or DEFAULT_MODEL,
            art_style=art_style,
            **image_config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {e}")
    return results
