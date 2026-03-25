from __future__ import annotations

import logging
import json
import re
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.story_context import StoryContext, build_story_context
from app.services import story_repository as repo
from app.services.llm.factory import get_llm_provider


_logger = logging.getLogger(__name__)


APPEARANCE_SYSTEM_PROMPT = """
You extract stable visual anchors for image and video generation.

Return strict JSON only in this shape:
{
  "characters": {
    "Character Name": {
      "body": "immutable physical traits only, in concise English, max 18 words",
      "clothing": "default outfit only, in concise English, max 12 words",
      "negative_prompt": "optional contamination exclusions only, max 12 words"
    }
  }
}

Rules:
- Keep only immutable appearance traits in body: age bracket, gender presentation, hair color/style, eye color, skin tone, build, distinctive facial traits.
- Keep clothing to the normal default outfit, not scene-specific actions or poses.
- Exclude lighting, background, camera words, emotions, personality, role arc, story summary, studio terms, art tags.
- Output concise English phrases suitable for image/video prompting.
""".strip()

SCENE_STYLE_SYSTEM_PROMPT = """
You compress story setting into compact visual consistency anchors for image and video generation.

Return strict JSON only in this shape:
{
  "styles": [
    {
      "keywords": ["optional short keyword", "optional location keyword"],
      "image_extra": "short visual environment anchors for still-image generation, concise English, max 18 words",
      "video_extra": "short motion-safe environment anchors for video generation, concise English, max 16 words",
      "negative_prompt": "optional concise exclusions, max 12 words"
    }
  ]
}

Rules:
- Prefer production-design anchors: architecture, materials, props, atmosphere, era cues.
- Do not repeat camera instructions, movement, dialogue, plot events, or art-style tags.
- Keep the output compact and globally reusable across many shots.
- If the setting is historical or ancient, include concise exclusions against modern intrusions when useful.
""".strip()


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _trim_words(text: str, limit: int) -> str:
    words = _collapse_spaces(text).split()
    if len(words) <= limit:
        return _collapse_spaces(text).strip(" ,.;:!?，。；：！？、")
    return " ".join(words[:limit]).strip(" ,.;:!?，。；：！？、")


def _parse_json(content: str) -> dict[str, Any]:
    normalized = content.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", normalized, flags=re.IGNORECASE)
    if fenced:
        normalized = fenced.group(1)
    elif normalized.startswith("```"):
            normalized = re.sub(r"^```(?:json)?\s*", "", normalized, flags=re.IGNORECASE)
    return json.loads(normalized.strip())


def _needs_appearance_cache(story: Mapping[str, Any]) -> bool:
    characters = list(story.get("characters") or [])
    meta = dict(story.get("meta") or {})
    cached = dict(meta.get("character_appearance_cache") or {})
    if not characters:
        return False
    return any(character.get("name") and character.get("name") not in cached for character in characters)


def _needs_scene_style_cache(story: Mapping[str, Any]) -> bool:
    meta = dict(story.get("meta") or {})
    cached = meta.get("scene_style_cache") or []
    return bool(story.get("selected_setting")) and not cached


async def extract_character_appearance(
    story: Mapping[str, Any],
    *,
    provider: str,
    model: str = "",
    api_key: str = "",
    base_url: str = "",
) -> dict[str, dict[str, str]]:
    characters = list(story.get("characters") or [])
    if not characters:
        return {}

    llm = get_llm_provider(provider, model=model, api_key=api_key, base_url=base_url)
    character_payload = [
        {
            "name": character.get("name", ""),
            "role": character.get("role", ""),
            "description": character.get("description", ""),
        }
        for character in characters
        if character.get("name")
    ]
    raw, _ = await llm.complete_messages_with_usage(
        system=APPEARANCE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract stable appearance anchors for these characters.\n"
                    f"{json.dumps(character_payload, ensure_ascii=False)}"
                ),
                "cacheable": True,
            }
        ],
        temperature=0.1,
        enable_caching=True,
    )
    data = _parse_json(raw)
    parsed = data.get("characters") or {}
    output: dict[str, dict[str, str]] = {}
    if not isinstance(parsed, Mapping):
        return output

    for character in characters:
        name = character.get("name", "")
        if not name:
            continue
        entry = parsed.get(name) or {}
        if not isinstance(entry, Mapping):
            continue
        output[name] = {
            "body": _trim_words(str(entry.get("body", "")), 18),
            "clothing": _trim_words(str(entry.get("clothing", "")), 12),
            "negative_prompt": _trim_words(str(entry.get("negative_prompt", "")), 12),
        }
    return {name: value for name, value in output.items() if any(value.values())}


async def extract_scene_style_cache(
    story: Mapping[str, Any],
    *,
    provider: str,
    model: str = "",
    api_key: str = "",
    base_url: str = "",
) -> list[dict[str, Any]]:
    world_summary = _collapse_spaces(str(story.get("selected_setting", "")))
    if not world_summary:
        return []

    llm = get_llm_provider(provider, model=model, api_key=api_key, base_url=base_url)
    raw, _ = await llm.complete_messages_with_usage(
        system=SCENE_STYLE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Compress this story setting into reusable scene-style anchors.\n"
                    f"Genre: {story.get('genre', '')}\n"
                    f"World Summary: {world_summary}"
                ),
                "cacheable": True,
            }
        ],
        temperature=0.1,
        enable_caching=True,
    )
    data = _parse_json(raw)
    styles = data.get("styles") or []
    if not isinstance(styles, list):
        return []

    output: list[dict[str, Any]] = []
    for style in styles:
        if not isinstance(style, Mapping):
            continue
        keywords = style.get("keywords") or []
        if not isinstance(keywords, list):
            keywords = []
        image_extra = _trim_words(str(style.get("image_extra", "")), 18)
        video_extra = _trim_words(str(style.get("video_extra", "")), 16)
        negative_prompt = _trim_words(str(style.get("negative_prompt", "")), 12)
        if image_extra or video_extra or negative_prompt:
            output.append(
                {
                    "keywords": [_collapse_spaces(str(keyword)) for keyword in keywords if str(keyword).strip()],
                    "image_extra": image_extra,
                    "video_extra": video_extra,
                    "negative_prompt": negative_prompt,
                }
            )
    return output[:3]


async def _project_visual_dna(
    db: AsyncSession,
    story_id: str,
    story: Mapping[str, Any],
    appearance_cache: Mapping[str, Mapping[str, str]],
) -> None:
    existing_images = dict(story.get("character_images") or {})
    updates: dict[str, dict[str, Any]] = {}

    for name, appearance in appearance_cache.items():
        body = _collapse_spaces(str(appearance.get("body", "")))
        if not body:
            continue
        current = dict(existing_images.get(name) or {})
        if _collapse_spaces(str(current.get("visual_dna", ""))) == body:
            continue
        current["visual_dna"] = body
        updates[name] = current

    if updates:
        await repo.upsert_character_images(db, story_id, updates)


async def prepare_story_context(
    db: AsyncSession,
    story_id: str | None,
    *,
    provider: str = "",
    model: str = "",
    api_key: str = "",
    base_url: str = "",
) -> tuple[dict[str, Any], StoryContext | None]:
    if not story_id:
        return {}, None

    story = await repo.get_story(db, story_id)
    if not story:
        return {}, None

    can_call_llm = bool(provider and api_key)

    if can_call_llm and _needs_appearance_cache(story):
        try:
            appearance_cache = dict((story.get("meta") or {}).get("character_appearance_cache") or {})
            extracted = await extract_character_appearance(
                story,
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
            )
            if extracted:
                appearance_cache.update(extracted)
                await repo.upsert_story_meta_cache(db, story_id, "character_appearance_cache", appearance_cache)
                await _project_visual_dna(db, story_id, story, appearance_cache)
                story = await repo.get_story(db, story_id)
        except Exception:
            _logger.exception("Failed to extract character appearance cache for story_id=%s", story_id)

    if can_call_llm and _needs_scene_style_cache(story):
        try:
            styles = await extract_scene_style_cache(
                story,
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
            )
            if styles:
                await repo.upsert_story_meta_cache(db, story_id, "scene_style_cache", styles)
                story = await repo.get_story(db, story_id)
        except Exception:
            _logger.exception("Failed to extract scene style cache for story_id=%s", story_id)

    return story, build_story_context(story)
