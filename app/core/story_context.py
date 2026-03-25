from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.core.api_keys import inject_art_style


_CLOTHING_HINTS = (
    "wearing",
    "dressed",
    "coat",
    "robe",
    "shirt",
    "dress",
    "armor",
    "uniform",
    "hanfu",
    "kimono",
    "jacket",
    "衣",
    "袍",
    "衫",
    "裙",
    "甲",
    "服",
)
_WARDROBE_CHANGE_HINTS = (
    "change outfit",
    "changes outfit",
    "changed outfit",
    "puts on",
    "takes off",
    "换装",
    "换上",
    "脱下",
    "更衣",
)
_GENRE_STYLE_RULES: dict[str, tuple[str, str, str]] = {
    "古风": (
        "ancient Chinese architecture, traditional props, weathered wood, period-authentic details",
        "ancient Chinese environment, traditional structures, era-consistent props",
        "modern buildings, modern clothing, cars, electric lights, plastic materials",
    ),
    "仙侠": (
        "ancient Chinese fantasy setting, flowing robes, mist, mystical natural atmosphere",
        "ancient Chinese fantasy environment, flowing robes, mystical atmosphere",
        "modern buildings, modern clothing, cars, electric lights, plastic materials",
    ),
    "武侠": (
        "martial-arts period setting, traditional architecture, grounded practical props",
        "martial-arts period environment, traditional structures, grounded props",
        "modern buildings, modern clothing, cars, electric lights, plastic materials",
    ),
    "历史": (
        "period-authentic architecture, era-consistent props, historical material details",
        "historical environment, period-authentic architecture, era-consistent props",
        "modern buildings, modern clothing, cars, electric lights, plastic materials",
    ),
    "宫斗": (
        "palace interiors, court costume materials, carved wood, silk textures, period detail",
        "palace environment, court costume textures, period-authentic atmosphere",
        "modern buildings, modern clothing, cars, electric lights, plastic materials",
    ),
    "科幻": (
        "futuristic environment, advanced interfaces, coherent sci-fi production design",
        "futuristic environment, coherent sci-fi design, advanced interfaces",
        "",
    ),
    "赛博": (
        "cyberpunk urban atmosphere, neon practical lighting, dense futuristic details",
        "cyberpunk city environment, practical neon lighting, dense futuristic details",
        "",
    ),
}


@dataclass
class CharacterLock:
    body_features: str = ""
    default_clothing: str = ""
    negative_prompt: str = ""


@dataclass
class SceneStyle:
    keywords: list[str] = field(default_factory=list)
    image_extra: str = ""
    video_extra: str = ""
    negative_prompt: str = ""


@dataclass
class StoryContext:
    base_art_style: str = ""
    scene_styles: list[SceneStyle] = field(default_factory=list)
    global_negative_prompt: str = ""
    character_locks: dict[str, CharacterLock] = field(default_factory=dict)
    clean_character_section: str = ""
    cache_fingerprint: str = ""


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _trim_words(text: str, limit: int) -> str:
    words = _collapse_spaces(text).split()
    if len(words) <= limit:
        return _collapse_spaces(text).strip(" ,.;:!?，。；：！？、")
    return " ".join(words[:limit]).strip(" ,.;:!?，。；：！？、")


def _trim_chars(text: str, limit: int) -> str:
    normalized = _collapse_spaces(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip(" ,.;:!?，。；：！？、")


def _sentence(text: str, lang: str, prefix: str = "") -> str:
    normalized = _collapse_spaces(text)
    if not normalized:
        return ""
    if prefix:
        normalized = f"{prefix}{normalized}"
    return f"{normalized}。" if lang == "zh" else f"{normalized}."


def normalize_cache_block(text: str) -> str:
    normalized = text or ""
    normalized = re.sub(r"Generated at:\s*[^\n]+", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"request[_ -]?id:\s*[^\n]+", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )
    return _collapse_spaces(normalized)


def get_cache_fingerprint(story_ctx: StoryContext, system_prompt: str, stable_blocks: list[str]) -> str:
    normalized_blocks = [
        normalize_cache_block(system_prompt),
        normalize_cache_block(story_ctx.clean_character_section),
        normalize_cache_block(story_ctx.base_art_style),
        *[normalize_cache_block(block) for block in stable_blocks],
    ]
    payload = "\n\n".join(block for block in normalized_blocks if block)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest() if payload else ""


def _extract_description_fragment(text: str, hints: tuple[str, ...], word_limit: int) -> str:
    if not text:
        return ""
    parts = re.split(r"[，。；;,.]", text)
    matched = [part.strip() for part in parts if any(hint in part.lower() for hint in hints)]
    if matched:
        return _trim_words(", ".join(matched), word_limit)
    return ""


def _guess_body_features(description: str) -> str:
    if not description:
        return ""
    fragments = re.split(r"[。；;]", description)
    selected = [frag.strip() for frag in fragments if frag.strip()]
    if not selected:
        return ""
    return _trim_words(selected[0], 25)


def _guess_default_clothing(description: str) -> str:
    return _extract_description_fragment(description, _CLOTHING_HINTS, 18)


def _build_scene_styles(story: Mapping[str, Any]) -> list[SceneStyle]:
    genre = _collapse_spaces(str(story.get("genre", "")))
    meta = dict(story.get("meta") or {})
    cached_styles = meta.get("scene_style_cache") or []
    styles: list[SceneStyle] = []

    if genre:
        for key, (image_extra, video_extra, negative_prompt) in _GENRE_STYLE_RULES.items():
            if key in genre:
                styles.append(
                    SceneStyle(
                        keywords=[key],
                        image_extra=image_extra,
                        video_extra=video_extra,
                        negative_prompt=negative_prompt,
                    )
                )
                break

    if isinstance(cached_styles, list):
        for entry in cached_styles:
            if not isinstance(entry, Mapping):
                continue
            keywords = entry.get("keywords") or []
            if not isinstance(keywords, list):
                keywords = []
            image_extra = _collapse_spaces(str(entry.get("image_extra", "")))
            video_extra = _collapse_spaces(str(entry.get("video_extra", "")))
            negative_prompt = _collapse_spaces(str(entry.get("negative_prompt", "")))
            if image_extra or video_extra or negative_prompt:
                styles.append(
                    SceneStyle(
                        keywords=[_collapse_spaces(str(keyword)) for keyword in keywords if str(keyword).strip()],
                        image_extra=image_extra,
                        video_extra=video_extra,
                        negative_prompt=negative_prompt,
                    )
                )

    return styles


def build_clean_character_section(character_locks: dict[str, CharacterLock], characters: list[dict]) -> str:
    if not characters:
        return ""

    lines = ["## Character Reference (maintain exact physical consistency across all shots)"]
    for character in characters:
        name = character.get("name", "")
        role = character.get("role", "")
        desc = character.get("description", "")
        if not name:
            continue

        lock = character_locks.get(name, CharacterLock())
        lines.append(f"- **{name}**（{role}）：{desc}")

        visual_bits = [bit for bit in (lock.body_features, lock.default_clothing) if bit]
        if visual_bits:
            lines.append(f"  Visual DNA: {'; '.join(visual_bits)}")
        else:
            lines.append("  Visual DNA: use the character description conservatively; do not invent new traits")

    return "\n".join(lines)


def build_story_context(story: Mapping[str, Any]) -> StoryContext:
    characters = list(story.get("characters") or [])
    character_images = dict(story.get("character_images") or {})
    meta = dict(story.get("meta") or {})
    cached_appearance = dict(meta.get("character_appearance_cache") or {})

    character_locks: dict[str, CharacterLock] = {}
    for character in characters:
        name = character.get("name", "")
        if not name:
            continue

        cached_entry = cached_appearance.get(name) or {}
        image_entry = character_images.get(name) or {}
        description = _collapse_spaces(str(character.get("description", "")))

        body = _collapse_spaces(str(cached_entry.get("body", ""))) if isinstance(cached_entry, dict) else ""
        clothing = _collapse_spaces(str(cached_entry.get("clothing", ""))) if isinstance(cached_entry, dict) else ""
        negative_prompt = _collapse_spaces(str(cached_entry.get("negative_prompt", ""))) if isinstance(cached_entry, dict) else ""

        if not body:
            body = _collapse_spaces(str(image_entry.get("visual_dna", ""))) or _guess_body_features(description)
        if not clothing:
            clothing = _guess_default_clothing(description)

        character_locks[name] = CharacterLock(
            body_features=body,
            default_clothing=clothing,
            negative_prompt=negative_prompt,
        )

    scene_styles = _build_scene_styles(story)
    global_negative_prompt = _collapse_spaces(
        ", ".join(
            dict.fromkeys(
                style.negative_prompt
                for style in scene_styles
                if style.negative_prompt
            )
        )
    )
    clean_character_section = build_clean_character_section(character_locks, characters)
    ctx = StoryContext(
        base_art_style=_collapse_spaces(str(story.get("art_style", ""))),
        scene_styles=scene_styles,
        global_negative_prompt=global_negative_prompt,
        character_locks=character_locks,
        clean_character_section=clean_character_section,
    )
    stable_blocks = [
        str(story.get("selected_setting", "")),
        *[style.image_extra for style in scene_styles],
        *[style.video_extra for style in scene_styles],
    ]
    ctx.cache_fingerprint = get_cache_fingerprint(ctx, "", stable_blocks)
    return ctx


def _shot_field(shot: ShotLike, field: str, default: Any = "") -> Any:
    if isinstance(shot, Mapping):
        return shot.get(field, default)
    return getattr(shot, field, default)


def _get_visual_field(shot: ShotLike, field: str) -> str:
    if isinstance(shot, Mapping):
        visual_elements = shot.get("visual_elements") or {}
        if isinstance(visual_elements, Mapping):
            return _collapse_spaces(str(visual_elements.get(field, "")))
        return ""
    visual_elements = getattr(shot, "visual_elements", None)
    if not visual_elements:
        return ""
    return _collapse_spaces(str(getattr(visual_elements, field, "")))


ShotLike = Mapping[str, Any] | Any


def _shot_character_names(shot: ShotLike) -> list[str]:
    for field in ("characters", "character_names", "mentioned_characters", "cast", "participants"):
        raw = _shot_field(shot, field, None)
        if raw is None:
            continue
        if isinstance(raw, str):
            values = [raw]
        elif isinstance(raw, (list, tuple, set)):
            values = list(raw)
        else:
            continue

        names: list[str] = []
        for value in values:
            if isinstance(value, Mapping):
                candidate = value.get("name", "")
            else:
                candidate = value
            normalized = _collapse_spaces(str(candidate))
            if normalized:
                names.append(normalized)
        if names:
            return names
    return []


def _shot_text_haystack(shot: ShotLike, *, include_last_frame: bool = True) -> str:
    parts = [
        str(_shot_field(shot, "storyboard_description", "")),
        str(_shot_field(shot, "image_prompt", "")),
        str(_shot_field(shot, "final_video_prompt", "")),
        _get_visual_field(shot, "subject_and_clothing"),
        _get_visual_field(shot, "action_and_expression"),
        _get_visual_field(shot, "environment_and_props"),
    ]
    if include_last_frame:
        parts.append(str(_shot_field(shot, "last_frame_prompt", "")))
    return _collapse_spaces(" ".join(parts))


def _safe_name_match(name: str, haystack: str) -> bool:
    normalized_name = _collapse_spaces(name)
    normalized_haystack = _collapse_spaces(haystack)
    if not normalized_name or not normalized_haystack:
        return False

    if re.search(r"\b" + re.escape(normalized_name) + r"\b", normalized_haystack, flags=re.IGNORECASE):
        return True

    # Fallback for CJK names where \b does not split between adjacent ideographs.
    return bool(
        re.search(
            r"(?<![A-Za-z0-9_])" + re.escape(normalized_name) + r"(?![A-Za-z0-9_])",
            normalized_haystack,
            flags=re.IGNORECASE,
        )
    )


def character_appears_in_shot(name: str, shot: ShotLike) -> bool:
    normalized_name = _collapse_spaces(name)
    if not normalized_name:
        return False

    structured_names = _shot_character_names(shot)
    if structured_names:
        return any(candidate.casefold() == normalized_name.casefold() for candidate in structured_names)

    return _safe_name_match(normalized_name, _shot_text_haystack(shot))


def should_inject_clothing_for(name: str, shot: ShotLike) -> bool:
    haystack = _collapse_spaces(
        " ".join(
            [
                str(_shot_field(shot, "storyboard_description", "")),
                str(_shot_field(shot, "image_prompt", "")),
                str(_shot_field(shot, "final_video_prompt", "")),
                _get_visual_field(shot, "action_and_expression"),
            ]
        )
    )
    if not _safe_name_match(name, haystack):
        return False
    lowered_haystack = haystack.lower()
    return not any(hint in lowered_haystack for hint in _WARDROBE_CHANGE_HINTS)


def _appearance_prefix(shot: ShotLike, ctx: StoryContext, include_clothing: bool = True) -> str:
    appearance_lines = []
    for name, lock in ctx.character_locks.items():
        if not character_appears_in_shot(name, shot):
            continue
        bits = [lock.body_features]
        if include_clothing and should_inject_clothing_for(name, shot) and lock.default_clothing:
            bits.append(lock.default_clothing)
        merged = ", ".join(bit for bit in bits if bit)
        if merged:
            appearance_lines.append(f"{name}: {merged}")

    if not appearance_lines:
        return ""

    base_prompt = " ".join(
        [
            str(_shot_field(shot, "image_prompt", "")),
            str(_shot_field(shot, "final_video_prompt", "")),
            str(_shot_field(shot, "last_frame_prompt", "")),
        ]
    )
    lang = "zh" if _contains_cjk(base_prompt) else "en"
    prefix = "角色锚点：" if lang == "zh" else "Character anchor: "
    suffix = "。" if lang == "zh" else "."
    return f"{prefix}{'; '.join(appearance_lines)}{suffix}"


def _scene_style_extra(ctx: StoryContext, shot: ShotLike, mode: str) -> str:
    if not ctx.scene_styles:
        return ""
    text = " ".join(
        [
            str(_shot_field(shot, "storyboard_description", "")),
            str(_shot_field(shot, "image_prompt", "")),
            str(_shot_field(shot, "final_video_prompt", "")),
            _get_visual_field(shot, "environment_and_props"),
        ]
    ).lower()
    matched = []
    for style in ctx.scene_styles:
        style_extra = style.image_extra if mode != "video" else (style.video_extra or style.image_extra)
        if not style_extra:
            continue
        if not style.keywords or any(keyword.lower() in text for keyword in style.keywords):
            matched.append(style_extra)
    if not matched and len(ctx.scene_styles) == 1:
        fallback_style = ctx.scene_styles[0]
        style_extra = fallback_style.image_extra if mode != "video" else (fallback_style.video_extra or fallback_style.image_extra)
        if style_extra:
            matched.append(style_extra)
    return _collapse_spaces("; ".join(matched))


def _merge_prompt(base_prompt: str, appearance_prefix: str, scene_extra: str, art_style: str) -> str:
    parts = [part for part in (_collapse_spaces(base_prompt), appearance_prefix, scene_extra) if part]
    merged = " ".join(parts)
    return inject_art_style(merged, art_style)


def _split_negative_terms(negative: str) -> list[str]:
    return [
        _collapse_spaces(term)
        for term in re.split(r"[,，]", negative)
        if _collapse_spaces(term)
    ]


def build_negative_prompt(shot: ShotLike, ctx: StoryContext | None) -> str:
    shot_negative_prompt = _collapse_spaces(str(_shot_field(shot, "negative_prompt", "")))
    if not ctx:
        return shot_negative_prompt

    negatives: list[str] = []
    if shot_negative_prompt:
        negatives.append(shot_negative_prompt)
    if ctx.global_negative_prompt:
        negatives.append(ctx.global_negative_prompt)
    for name, lock in ctx.character_locks.items():
        if character_appears_in_shot(name, shot) and lock.negative_prompt:
            negatives.append(lock.negative_prompt)
    normalized_terms: list[str] = []
    for negative in negatives:
        normalized_terms.extend(_split_negative_terms(negative))
    return _collapse_spaces(", ".join(dict.fromkeys(normalized_terms)))


def build_image_generation_prompt(shot: ShotLike, ctx: StoryContext | None, art_style: str = "") -> str:
    base_prompt = str(_shot_field(shot, "image_prompt", "") or _shot_field(shot, "final_video_prompt", ""))
    if not ctx:
        return inject_art_style(base_prompt, art_style)
    return _merge_prompt(
        base_prompt,
        _appearance_prefix(shot, ctx, include_clothing=True),
        _scene_style_extra(ctx, shot, "image"),
        art_style or ctx.base_art_style,
    )


def build_video_generation_prompt(shot: ShotLike, ctx: StoryContext | None, art_style: str = "") -> str:
    base_prompt = str(_shot_field(shot, "final_video_prompt", "") or _shot_field(shot, "image_prompt", ""))
    if not ctx:
        return inject_art_style(base_prompt, art_style)
    return _merge_prompt(
        base_prompt,
        _appearance_prefix(shot, ctx, include_clothing=True),
        _scene_style_extra(ctx, shot, "video"),
        art_style or ctx.base_art_style,
    )


def build_last_frame_generation_prompt(shot: ShotLike, ctx: StoryContext | None, art_style: str = "") -> str:
    base_prompt = str(_shot_field(shot, "last_frame_prompt", ""))
    if not base_prompt:
        return ""
    if not ctx:
        return inject_art_style(base_prompt, art_style)
    return _merge_prompt(
        base_prompt,
        _appearance_prefix(shot, ctx, include_clothing=True),
        _scene_style_extra(ctx, shot, "image"),
        art_style or ctx.base_art_style,
    )


def build_generation_payload(shot: ShotLike, ctx: StoryContext | None, art_style: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "shot_id": str(_shot_field(shot, "shot_id", "")),
        "image_prompt": build_image_generation_prompt(shot, ctx, art_style=art_style),
        "final_video_prompt": build_video_generation_prompt(shot, ctx, art_style=art_style),
    }

    last_frame_prompt = build_last_frame_generation_prompt(shot, ctx, art_style=art_style)
    if last_frame_prompt:
        payload["last_frame_prompt"] = last_frame_prompt

    negative_prompt = build_negative_prompt(shot, ctx)
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    return payload
