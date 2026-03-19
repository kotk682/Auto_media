import asyncio
import httpx
from pathlib import Path

from app.core.config import settings

IMAGE_DIR = Path("media/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell"
IMAGE_SIZE = "1280x720"


async def generate_image(visual_prompt: str, shot_id: str, model: str = DEFAULT_MODEL) -> dict:
    """Generate image for a single shot. Returns { shot_id, image_path, image_url }."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.siliconflow_base_url}/images/generations",
            headers={"Authorization": f"Bearer {settings.siliconflow_api_key}"},
            json={"model": model, "prompt": visual_prompt, "n": 1, "image_size": IMAGE_SIZE},
        )
        print(f"[IMAGE] status={resp.status_code} body={resp.text[:500]}")
        resp.raise_for_status()
        image_url = resp.json()["images"][0]["url"]

        # Download and save locally
        img_resp = await client.get(image_url)
        img_resp.raise_for_status()

    output_path = IMAGE_DIR / f"{shot_id}.png"
    output_path.write_bytes(img_resp.content)

    return {
        "shot_id": shot_id,
        "image_path": str(output_path),
        "image_url": f"/media/images/{shot_id}.png",
    }


async def generate_images_batch(shots: list[dict], model: str = DEFAULT_MODEL) -> list[dict]:
    """Generate images for all shots concurrently."""
    tasks = [generate_image(shot["visual_prompt"], shot["shot_id"], model) for shot in shots]
    return list(await asyncio.gather(*tasks))
