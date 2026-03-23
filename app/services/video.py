import asyncio
from pathlib import Path

import httpx

from app.services.video_providers.factory import get_video_provider

VIDEO_DIR = Path("media/videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "wan2.6-i2v-flash"
DEFAULT_PROVIDER = "dashscope"


async def generate_video(
    image_url: str,
    prompt: str,
    shot_id: str,
    model: str = DEFAULT_MODEL,
    video_api_key: str = "",
    video_base_url: str = "",
    video_provider: str = DEFAULT_PROVIDER,
) -> dict:
    """Generate video for a single shot. Returns { shot_id, video_path, video_url }."""
    provider = get_video_provider(video_provider)
    remote_url = await provider.generate(image_url, prompt, model, video_api_key, video_base_url)

    async with httpx.AsyncClient(timeout=60) as client:
        vid_resp = await client.get(remote_url)
        vid_resp.raise_for_status()

    output_path = VIDEO_DIR / f"{shot_id}.mp4"
    output_path.write_bytes(vid_resp.content)

    return {
        "shot_id": shot_id,
        "video_path": str(output_path),
        "video_url": f"/media/videos/{shot_id}.mp4",
    }


async def generate_videos_batch(
    shots: list[dict],
    base_url: str,
    model: str = DEFAULT_MODEL,
    video_api_key: str = "",
    video_base_url: str = "",
    video_provider: str = DEFAULT_PROVIDER,
) -> list[dict]:
    """
    Generate videos for all shots concurrently.
    Each shot must have: shot_id, image_url (relative), visual_prompt, camera_motion.
    base_url: server base URL to convert relative image_url to absolute.
    """
    tasks = [
        generate_video(
            image_url=f"{base_url}{shot['image_url']}",
            prompt=f"{shot['visual_prompt']} {shot['camera_motion']}",
            shot_id=shot["shot_id"],
            model=model,
            video_api_key=video_api_key,
            video_base_url=video_base_url,
            video_provider=video_provider,
        )
        for shot in shots
        if shot.get("image_url")
    ]
    return list(await asyncio.gather(*tasks))
