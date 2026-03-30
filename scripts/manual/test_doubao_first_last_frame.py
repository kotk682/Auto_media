#!/usr/bin/env python3
"""
Manual first/last-frame integration script.

Usage:
    python scripts/manual/test_doubao_first_last_frame.py
"""

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.image import generate_image
from app.services.video import generate_video


IMAGE_API_KEY = (
    os.getenv("TEST_IMAGE_API_KEY")
    or os.getenv("SILICONFLOW_IMAGE_API_KEY")
    or os.getenv("SILICONFLOW_API_KEY", "")
)
VIDEO_API_KEY = (
    os.getenv("TEST_DOUBAO_VIDEO_API_KEY")
    or os.getenv("DOUBAO_VIDEO_API_KEY")
    or os.getenv("DOUBAO_API_KEY", "")
)
VIDEO_BASE_URL = (
    os.getenv("TEST_DOUBAO_BASE_URL")
    or os.getenv("DOUBAO_VIDEO_BASE_URL")
    or os.getenv("DOUBAO_BASE_URL")
    or "https://ark.cn-beijing.volces.com/api/v3"
)
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def _require_manual_env() -> None:
    missing: list[str] = []
    if not IMAGE_API_KEY:
        missing.append("TEST_IMAGE_API_KEY or SILICONFLOW_IMAGE_API_KEY")
    if not VIDEO_API_KEY:
        missing.append("TEST_DOUBAO_VIDEO_API_KEY or DOUBAO_VIDEO_API_KEY")
    if missing:
        raise RuntimeError(
            "Manual first/last-frame test requires env vars: " + ", ".join(missing)
        )


def _normalize_media_url(image_url: str) -> str:
    parsed = urlparse(image_url)
    if parsed.scheme and parsed.netloc:
        return image_url
    return urljoin(f"{BASE_URL.rstrip('/')}/", image_url.lstrip("/"))


async def run_single_frame_i2v():
    print("\n" + "=" * 80)
    print("Test 1: single-frame I2V baseline")
    print("=" * 80)

    first_frame = await generate_image(
        visual_prompt=(
            "A young man stands at an office doorway, blue shirt, modern office background, "
            "warm morning light, cinematic look, 4k"
        ),
        shot_id="test_single_firstframe",
        model="black-forest-labs/FLUX.1-schnell",
        image_api_key=IMAGE_API_KEY,
        image_base_url="",
    )

    video = await generate_video(
        image_url=_normalize_media_url(first_frame["image_url"]),
        prompt="The young man walks from the doorway to the desk and sits down.",
        shot_id="test_single_i2v",
        model="doubao-seedance-1-5-pro-251215",
        video_api_key=VIDEO_API_KEY,
        video_base_url=VIDEO_BASE_URL,
        video_provider="doubao",
    )

    print(f"First frame: {first_frame['image_url']}")
    print(f"Video: {video['video_url']}")
    return first_frame, video


async def run_first_last_frame_transition():
    print("\n" + "=" * 80)
    print("Test 2: first/last-frame transition")
    print("=" * 80)

    first_frame = await generate_image(
        visual_prompt=(
            "A young man stands at an office doorway, blue shirt, standing pose, "
            "modern office background, warm morning light, cinematic look, 4k"
        ),
        shot_id="test_transition_firstframe",
        model="black-forest-labs/FLUX.1-schnell",
        image_api_key=IMAGE_API_KEY,
        image_base_url="",
    )

    last_frame = await generate_image(
        visual_prompt=(
            "A young man sits on an office chair, blue shirt, hands on knees, "
            "modern office background, warm morning light, cinematic look, 4k"
        ),
        shot_id="test_transition_lastframe",
        model="black-forest-labs/FLUX.1-schnell",
        image_api_key=IMAGE_API_KEY,
        image_base_url="",
    )

    video = await generate_video(
        image_url=_normalize_media_url(first_frame["image_url"]),
        prompt="Transition naturally from standing to sitting in the chair.",
        shot_id="test_transition_video",
        model="doubao-seedance-1-5-pro-251215",
        video_api_key=VIDEO_API_KEY,
        video_base_url=VIDEO_BASE_URL,
        video_provider="doubao",
        last_frame_url=_normalize_media_url(last_frame["image_url"]),
    )

    print(f"First frame: {first_frame['image_url']}")
    print(f"Last frame: {last_frame['image_url']}")
    print(f"Transition video: {video['video_url']}")
    return first_frame, last_frame, video


async def run_scene_transition():
    print("\n" + "=" * 80)
    print("Test 3: scene-to-scene transition")
    print("=" * 80)

    scene1_last = await generate_image(
        visual_prompt=(
            "A young man exits an office doorway, back view, looking back, "
            "modern office background, cinematic look, 4k"
        ),
        shot_id="test_scene1_lastframe",
        model="black-forest-labs/FLUX.1-schnell",
        image_api_key=IMAGE_API_KEY,
        image_base_url="",
    )

    scene2_first = await generate_image(
        visual_prompt=(
            "A young man walks into a meeting room, side view, modern meeting room background, "
            "natural light, cinematic look, 4k"
        ),
        shot_id="test_scene2_firstframe",
        model="black-forest-labs/FLUX.1-schnell",
        image_api_key=IMAGE_API_KEY,
        image_base_url="",
    )

    video = await generate_video(
        image_url=_normalize_media_url(scene1_last["image_url"]),
        prompt="A smooth scene transition from the office to the meeting room.",
        shot_id="test_scene_transition",
        model="doubao-seedance-1-5-pro-251215",
        video_api_key=VIDEO_API_KEY,
        video_base_url=VIDEO_BASE_URL,
        video_provider="doubao",
        last_frame_url=_normalize_media_url(scene2_first["image_url"]),
    )

    print(f"Scene 1 last frame: {scene1_last['image_url']}")
    print(f"Scene 2 first frame: {scene2_first['image_url']}")
    print(f"Transition video: {video['video_url']}")
    return scene1_last, scene2_first, video


async def main():
    _require_manual_env()
    print("\nManual Doubao first/last-frame test\n")

    try:
        await run_single_frame_i2v()
        await run_first_last_frame_transition()
        await run_scene_transition()
        print("\nAll manual checks completed.")
    except Exception as exc:
        print(f"\nTest failed: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
