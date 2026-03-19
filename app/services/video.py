import asyncio
import httpx
from pathlib import Path

from app.core.config import settings

VIDEO_DIR = Path("media/videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "wan2.6-i2v-flash"
DASHSCOPE_SUBMIT_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis"
DASHSCOPE_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"


async def _submit_task(client: httpx.AsyncClient, image_url: str, prompt: str, model: str) -> str:
    """Submit image-to-video task, return task_id."""
    resp = await client.post(
        DASHSCOPE_SUBMIT_URL,
        headers={
            "Authorization": f"Bearer {settings.qwen_api_key}",
            "X-DashScope-Async": "enable",
        },
        json={
            "model": model,
            "input": {"image_url": image_url, "prompt": prompt},
            "parameters": {"duration": 5},
        },
    )
    resp.raise_for_status()
    data = resp.json()
    task_id = data["output"]["task_id"]
    return task_id


async def _poll_task(client: httpx.AsyncClient, task_id: str, timeout: int = 300) -> str:
    """Poll task until succeeded, return video URL."""
    url = DASHSCOPE_TASK_URL.format(task_id=task_id)
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(5)
        resp = await client.get(url, headers={"Authorization": f"Bearer {settings.qwen_api_key}"})
        resp.raise_for_status()
        data = resp.json()
        status = data["output"]["task_status"]
        if status == "SUCCEEDED":
            return data["output"]["video_url"]
        if status in ("FAILED", "CANCELED"):
            raise RuntimeError(f"视频任务失败: {data['output'].get('message', status)}")
    raise TimeoutError(f"视频任务超时: {task_id}")


async def generate_video(image_url: str, prompt: str, shot_id: str, model: str = DEFAULT_MODEL) -> dict:
    """Generate video for a single shot. Returns { shot_id, video_path, video_url }."""
    # image_url must be a public URL; convert local path to full URL
    async with httpx.AsyncClient(timeout=30) as client:
        task_id = await _submit_task(client, image_url, prompt, model)

    async with httpx.AsyncClient(timeout=30) as client:
        remote_video_url = await _poll_task(client, task_id)

        # Download and save locally
        vid_resp = await client.get(remote_video_url)
        vid_resp.raise_for_status()

    output_path = VIDEO_DIR / f"{shot_id}.mp4"
    output_path.write_bytes(vid_resp.content)

    return {
        "shot_id": shot_id,
        "video_path": str(output_path),
        "video_url": f"/media/videos/{shot_id}.mp4",
    }


async def generate_videos_batch(shots: list[dict], base_url: str, model: str = DEFAULT_MODEL) -> list[dict]:
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
        )
        for shot in shots
        if shot.get("image_url")
    ]
    return list(await asyncio.gather(*tasks))
