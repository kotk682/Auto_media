from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Mapping
from app.schemas.pipeline import PipelineStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
else:
    AsyncSession = Any

logger = logging.getLogger(__name__)

STORYBOARD_GENERATION_META_KEY = "storyboard_generation"
_TRANSIENT_SHOT_KEYS = {"ttsLoading", "imageLoading", "videoLoading"}
_DEPRECATED_SHOT_KEYS = {"last_frame_prompt", "last_frame_url"}


def serialize_shot_for_storage(shot: Any) -> dict[str, Any]:
    if hasattr(shot, "model_dump"):
        data = shot.model_dump(mode="json")
    elif hasattr(shot, "dict"):
        data = shot.dict()
    else:
        data = dict(shot)
    return {
        key: deepcopy(value)
        for key, value in data.items()
        if key not in _TRANSIENT_SHOT_KEYS and key not in _DEPRECATED_SHOT_KEYS
    }


def load_storyboard_generation_state(story: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(story, Mapping):
        return {}
    meta = story.get("meta")
    if not isinstance(meta, Mapping):
        return {}
    state = meta.get(STORYBOARD_GENERATION_META_KEY)
    return deepcopy(dict(state)) if isinstance(state, Mapping) else {}


def _merge_generated_files(
    existing: Mapping[str, Any] | None,
    incoming: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = deepcopy(dict(existing)) if isinstance(existing, Mapping) else {}
    if not isinstance(incoming, Mapping):
        return merged

    for key, value in dict(incoming).items():
        if isinstance(merged.get(key), Mapping) and isinstance(value, Mapping):
            nested = deepcopy(dict(merged.get(key) or {}))
            nested.update(deepcopy(dict(value)))
            merged[key] = nested
            continue
        merged[key] = deepcopy(value)
    return merged


def collect_storyboard_shot_ids(shots: list[Any] | None) -> list[str]:
    ordered_ids: list[str] = []
    seen: set[str] = set()
    for shot in shots or []:
        if not isinstance(shot, Mapping):
            shot = serialize_shot_for_storage(shot)
        shot_id = str(shot.get("shot_id", "")).strip()
        if not shot_id or shot_id in seen:
            continue
        ordered_ids.append(shot_id)
        seen.add(shot_id)
    return ordered_ids


def collect_expected_transition_ids(shots: list[Any] | None) -> list[str]:
    shot_ids = collect_storyboard_shot_ids(shots)
    return [
        f"transition_{shot_ids[index]}__{shot_ids[index + 1]}"
        for index in range(len(shot_ids) - 1)
    ]


def build_storyboard_timeline(
    shots: list[Any] | None,
    transitions: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    shot_ids = collect_storyboard_shot_ids(shots)
    transition_map = dict(transitions or {})
    timeline: list[dict[str, str]] = []
    for index, shot_id in enumerate(shot_ids):
        timeline.append({"item_type": "shot", "item_id": shot_id})
        if index + 1 >= len(shot_ids):
            continue
        transition_id = f"transition_{shot_id}__{shot_ids[index + 1]}"
        transition = transition_map.get(transition_id) or {}
        if isinstance(transition, Mapping) and transition.get("video_url"):
            timeline.append({"item_type": "transition", "item_id": transition_id})
    return timeline


def _filter_shot_result_map(
    results: Mapping[str, Any] | None,
    valid_shot_ids: set[str],
) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for key, value in dict(results or {}).items():
        entry = value if isinstance(value, Mapping) else {}
        shot_id = str(entry.get("shot_id", key)).strip()
        if shot_id not in valid_shot_ids:
            continue
        filtered[shot_id] = deepcopy(value)
    return filtered


def _transition_references_invalidated_shot(
    transition_id: str,
    transition: Mapping[str, Any] | None,
    invalidated_shot_ids: set[str],
) -> bool:
    if not invalidated_shot_ids:
        return False
    if isinstance(transition, Mapping):
        from_shot_id = str(transition.get("from_shot_id", "")).strip()
        to_shot_id = str(transition.get("to_shot_id", "")).strip()
        if from_shot_id in invalidated_shot_ids or to_shot_id in invalidated_shot_ids:
            return True

    normalized_id = str(transition_id).strip()
    if normalized_id.startswith("transition_"):
        pair = normalized_id[len("transition_") :]
        if "__" in pair:
            from_shot_id, to_shot_id = pair.split("__", 1)
            if from_shot_id in invalidated_shot_ids or to_shot_id in invalidated_shot_ids:
                return True
    return False


def prune_generated_files_to_storyboard(
    generated_files: Mapping[str, Any] | None,
    shots: list[Any] | None,
) -> dict[str, Any]:
    pruned = deepcopy(dict(generated_files)) if isinstance(generated_files, Mapping) else {}
    shot_ids = set(collect_storyboard_shot_ids(shots))
    transition_ids = set(collect_expected_transition_ids(shots))

    for key in ("tts", "images", "videos"):
        if key not in pruned:
            continue
        pruned[key] = _filter_shot_result_map(pruned.get(key), shot_ids)

    if "transitions" in pruned:
        transitions = {}
        for transition_id, result in dict(pruned.get("transitions") or {}).items():
            normalized_id = str(transition_id or (result or {}).get("transition_id", "")).strip()
            if normalized_id not in transition_ids:
                continue
            transitions[normalized_id] = deepcopy(result)
        pruned["transitions"] = transitions

    if "shots" in pruned and isinstance(pruned.get("shots"), list):
        pruned["shots"] = [
            serialize_shot_for_storage(shot)
            for shot in pruned["shots"]
            if str((shot or {}).get("shot_id", "")).strip() in shot_ids
        ]

    if "timeline" in pruned or "transitions" in pruned:
        pruned["timeline"] = build_storyboard_timeline(shots, pruned.get("transitions"))

    return pruned


def _has_authoritative_storyboard_shots(shots: list[Any] | None) -> bool:
    return bool(collect_storyboard_shot_ids(shots))


def _filter_existing_timeline(
    timeline: Any,
    *,
    valid_transition_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    if not isinstance(timeline, list):
        return []

    filtered: list[dict[str, str]] = []
    for item in timeline:
        if not isinstance(item, Mapping):
            continue
        item_type = str(item.get("item_type", "")).strip()
        item_id = str(item.get("item_id", "")).strip()
        if not item_type or not item_id:
            continue
        if item_type == "transition" and valid_transition_ids is not None and item_id not in valid_transition_ids:
            continue
        filtered.append({"item_type": item_type, "item_id": item_id})
    return filtered


def invalidate_generated_files_for_shots(
    generated_files: Mapping[str, Any] | None,
    shots: list[Any] | None,
    invalidated_shot_ids: list[str] | None,
    *,
    clear_videos_for_invalidated_shots: bool = False,
    clear_final_video: bool = False,
) -> dict[str, Any]:
    invalidated_ids = {
        str(shot_id).strip()
        for shot_id in invalidated_shot_ids or []
        if str(shot_id).strip()
    }
    has_authoritative_shots = _has_authoritative_storyboard_shots(shots)
    if has_authoritative_shots:
        next_generated_files = prune_generated_files_to_storyboard(generated_files, shots)
    else:
        next_generated_files = deepcopy(dict(generated_files)) if isinstance(generated_files, Mapping) else {}

    if clear_videos_for_invalidated_shots and "videos" in next_generated_files:
        next_generated_files["videos"] = {
            shot_id: deepcopy(result)
            for shot_id, result in dict(next_generated_files.get("videos") or {}).items()
            if str((result or {}).get("shot_id", shot_id)).strip() not in invalidated_ids
        }

    if "transitions" in next_generated_files:
        next_generated_files["transitions"] = {
            transition_id: deepcopy(result)
            for transition_id, result in dict(next_generated_files.get("transitions") or {}).items()
            if not _transition_references_invalidated_shot(
                transition_id,
                result if isinstance(result, Mapping) else None,
                invalidated_ids,
            )
        }

    if has_authoritative_shots and ("timeline" in next_generated_files or "transitions" in next_generated_files):
        next_generated_files["timeline"] = build_storyboard_timeline(
            shots,
            next_generated_files.get("transitions"),
        )
    elif "timeline" in next_generated_files:
        next_generated_files["timeline"] = _filter_existing_timeline(
            next_generated_files.get("timeline"),
            valid_transition_ids=set(dict(next_generated_files.get("transitions") or {}).keys()),
        )

    if clear_final_video:
        next_generated_files.pop("final_video_url", None)

    return next_generated_files


def _merge_shots(
    existing_shots: list[dict[str, Any]],
    incoming_shots: list[Any],
    *,
    partial: bool,
) -> list[dict[str, Any]]:
    serialized_incoming = [serialize_shot_for_storage(shot) for shot in incoming_shots]
    if not partial:
        return serialized_incoming

    existing_map = {
        str(shot.get("shot_id", "")): deepcopy(shot)
        for shot in existing_shots
        if isinstance(shot, Mapping) and shot.get("shot_id")
    }
    incoming_order: list[str] = []
    for shot in serialized_incoming:
        shot_id = str(shot.get("shot_id", ""))
        if not shot_id:
            continue
        existing_map[shot_id] = {**existing_map.get(shot_id, {}), **shot}
        incoming_order.append(shot_id)

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for shot in existing_shots:
        if not isinstance(shot, Mapping):
            continue
        shot_id = str(shot.get("shot_id", ""))
        if not shot_id or shot_id not in existing_map:
            continue
        merged.append(deepcopy(existing_map[shot_id]))
        seen.add(shot_id)

    for shot_id in incoming_order:
        if shot_id in seen or shot_id not in existing_map:
            continue
        merged.append(deepcopy(existing_map[shot_id]))
        seen.add(shot_id)

    return merged


def _apply_generated_files_to_shots(
    shots: list[dict[str, Any]],
    generated_files: Mapping[str, Any] | None,
    *,
    clear_missing_sections: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(generated_files, Mapping):
        return shots

    shot_map = {
        str(shot.get("shot_id", "")): deepcopy(shot)
        for shot in shots
        if isinstance(shot, Mapping) and shot.get("shot_id")
    }

    def _ensure_shot(shot_id: str) -> dict[str, Any]:
        if shot_id not in shot_map:
            shot_map[shot_id] = {"shot_id": shot_id}
        return shot_map[shot_id]

    tts_entries = dict(generated_files.get("tts") or {}) if isinstance(generated_files.get("tts"), Mapping) else {}
    image_entries = dict(generated_files.get("images") or {}) if isinstance(generated_files.get("images"), Mapping) else {}
    video_entries = dict(generated_files.get("videos") or {}) if isinstance(generated_files.get("videos"), Mapping) else {}

    clear_missing_sections = set(clear_missing_sections or set())
    has_tts_entries = "tts" in generated_files or "tts" in clear_missing_sections
    has_image_entries = "images" in generated_files or "images" in clear_missing_sections
    has_video_entries = "videos" in generated_files or "videos" in clear_missing_sections

    for shot_id, shot in shot_map.items():
        if has_tts_entries and shot_id not in tts_entries:
            shot.pop("audio_url", None)
            shot.pop("audio_duration", None)
        if has_image_entries and shot_id not in image_entries:
            shot.pop("image_url", None)
            shot.pop("image_path", None)
            shot.pop("last_frame_url", None)
        if has_video_entries and shot_id not in video_entries:
            shot.pop("video_url", None)
            shot.pop("video_path", None)

    for result in tts_entries.values():
        if not isinstance(result, Mapping):
            continue
        shot_id = str(result.get("shot_id", ""))
        if not shot_id:
            continue
        shot = _ensure_shot(shot_id)
        shot["audio_url"] = result.get("audio_url")
        if result.get("duration_seconds") is not None:
            shot["audio_duration"] = result.get("duration_seconds")
        elif result.get("audio_duration") is not None:
            shot["audio_duration"] = result.get("audio_duration")

    for result in image_entries.values():
        if not isinstance(result, Mapping):
            continue
        shot_id = str(result.get("shot_id", ""))
        if not shot_id:
            continue
        shot = _ensure_shot(shot_id)
        shot["image_url"] = result.get("image_url")
        shot["image_path"] = result.get("image_path")
        shot.pop("last_frame_url", None)

    for result in video_entries.values():
        if not isinstance(result, Mapping):
            continue
        shot_id = str(result.get("shot_id", ""))
        if not shot_id:
            continue
        shot = _ensure_shot(shot_id)
        shot["video_url"] = result.get("video_url")
        if result.get("video_path") is not None:
            shot["video_path"] = result.get("video_path")

    ordered_ids = [str(shot.get("shot_id", "")) for shot in shots if isinstance(shot, Mapping) and shot.get("shot_id")]
    for shot_id in shot_map:
        if shot_id not in ordered_ids:
            ordered_ids.append(shot_id)
    return [deepcopy(shot_map[shot_id]) for shot_id in ordered_ids if shot_id]


def build_storyboard_generation_state(
    story: Mapping[str, Any] | None,
    *,
    shots: list[Any] | None = None,
    partial_shots: bool = False,
    usage: Mapping[str, Any] | None = None,
    generated_files: Mapping[str, Any] | None = None,
    pipeline_id: str = "",
    project_id: str = "",
    story_id: str = "",
    final_video_url: str | None = None,
    replace_generated_files: bool = False,
    prune_generated_files_to_shots: bool = False,
    invalidate_shot_ids: list[str] | None = None,
    clear_videos_for_invalidated_shots: bool = False,
    clear_final_video: bool = False,
) -> dict[str, Any]:
    state = load_storyboard_generation_state(story)
    state.setdefault("shots", [])

    if shots is not None:
        state["shots"] = _merge_shots(
            list(state.get("shots") or []),
            shots,
            partial=partial_shots,
        )
    if usage is not None:
        state["usage"] = deepcopy(dict(usage))
    next_generated_files = state.get("generated_files")
    should_refresh_shots_from_generated_files = False
    clear_missing_sections: set[str] = set()

    if generated_files is not None:
        if replace_generated_files:
            next_generated_files = deepcopy(dict(generated_files)) if isinstance(generated_files, Mapping) else {}
            clear_missing_sections = {"tts", "images", "videos"}
        else:
            next_generated_files = _merge_generated_files(
                next_generated_files,
                generated_files,
            )
        should_refresh_shots_from_generated_files = True
    elif isinstance(next_generated_files, Mapping):
        next_generated_files = deepcopy(dict(next_generated_files))

    if (
        prune_generated_files_to_shots
        and isinstance(next_generated_files, Mapping)
        and _has_authoritative_storyboard_shots(list(state.get("shots") or []))
    ):
        next_generated_files = prune_generated_files_to_storyboard(
            next_generated_files,
            list(state.get("shots") or []),
        )
        should_refresh_shots_from_generated_files = True

    if invalidate_shot_ids and isinstance(next_generated_files, Mapping):
        next_generated_files = invalidate_generated_files_for_shots(
            next_generated_files,
            list(state.get("shots") or []),
            invalidate_shot_ids,
            clear_videos_for_invalidated_shots=clear_videos_for_invalidated_shots,
            clear_final_video=clear_final_video,
        )
        should_refresh_shots_from_generated_files = True
    elif clear_final_video and isinstance(next_generated_files, Mapping):
        next_generated_files.pop("final_video_url", None)
        should_refresh_shots_from_generated_files = True

    if isinstance(next_generated_files, Mapping):
        state["generated_files"] = next_generated_files

    if should_refresh_shots_from_generated_files and isinstance(next_generated_files, Mapping):
        state["shots"] = _apply_generated_files_to_shots(
            list(state.get("shots") or []),
            next_generated_files,
            clear_missing_sections=clear_missing_sections,
        )
    if project_id:
        state["project_id"] = project_id
    if pipeline_id:
        state["pipeline_id"] = pipeline_id
    if story_id:
        state["story_id"] = story_id
    if final_video_url is not None:
        state["final_video_url"] = final_video_url
    elif clear_final_video:
        state["final_video_url"] = ""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    return state


async def persist_storyboard_generation_state(
    db: AsyncSession,
    *,
    story_id: str,
    story: Mapping[str, Any] | None,
    shots: list[Any] | None = None,
    partial_shots: bool = False,
    usage: Mapping[str, Any] | None = None,
    generated_files: Mapping[str, Any] | None = None,
    pipeline_id: str = "",
    project_id: str = "",
    final_video_url: str | None = None,
    replace_generated_files: bool = False,
    prune_generated_files_to_shots: bool = False,
    invalidate_shot_ids: list[str] | None = None,
    clear_videos_for_invalidated_shots: bool = False,
    clear_final_video: bool = False,
) -> dict[str, Any]:
    from app.services import story_repository as repo

    normalized_story_id = str(story_id or "").strip()
    if not normalized_story_id:
        logger.warning(
            "Skipping storyboard_generation persistence because story_id is empty. story_id=%r pipeline_id=%r project_id=%r",
            story_id,
            pipeline_id,
            project_id,
        )
        return {}
    state = build_storyboard_generation_state(
        story,
        shots=shots,
        partial_shots=partial_shots,
        usage=usage,
        generated_files=generated_files,
        pipeline_id=pipeline_id,
        project_id=project_id,
        story_id=normalized_story_id,
        final_video_url=final_video_url,
        replace_generated_files=replace_generated_files,
        prune_generated_files_to_shots=prune_generated_files_to_shots,
        invalidate_shot_ids=invalidate_shot_ids,
        clear_videos_for_invalidated_shots=clear_videos_for_invalidated_shots,
        clear_final_video=clear_final_video,
    )
    await repo.upsert_story_meta_cache(
        db,
        normalized_story_id,
        STORYBOARD_GENERATION_META_KEY,
        state,
    )
    return state


async def persist_generated_files_to_pipeline(
    db: AsyncSession,
    *,
    project_id: str,
    pipeline_id: str,
    story_id: str,
    generated_files: Mapping[str, Any] | None = None,
    final_video_url: str | None = None,
    shots: list[Any] | None = None,
    replace_generated_files: bool = False,
    prune_generated_files_to_shots: bool = False,
    invalidate_shot_ids: list[str] | None = None,
    clear_videos_for_invalidated_shots: bool = False,
    clear_final_video: bool = False,
) -> dict[str, Any]:
    from app.services import story_repository as repo

    normalized_pipeline_id = str(pipeline_id or "").strip()
    normalized_story_id = str(story_id or "").strip()
    if not normalized_pipeline_id or not normalized_story_id:
        logger.warning(
            "Skipping pipeline generated_files persistence because pipeline_id/story_id is empty. pipeline_id=%r story_id=%r normalized_pipeline_id=%r normalized_story_id=%r",
            pipeline_id,
            story_id,
            normalized_pipeline_id,
            normalized_story_id,
        )
        return {}

    existing_pipeline = await repo.get_pipeline(db, normalized_pipeline_id)
    if replace_generated_files:
        merged_generated_files = deepcopy(dict(generated_files)) if isinstance(generated_files, Mapping) else {}
    else:
        merged_generated_files = _merge_generated_files(
            existing_pipeline.get("generated_files"),
            generated_files,
        )

    authoritative_shots = [serialize_shot_for_storage(shot) for shot in shots or []]
    if not authoritative_shots:
        storyboard_payload = merged_generated_files.get("storyboard") if isinstance(merged_generated_files, Mapping) else None
        storyboard_shots = storyboard_payload.get("shots") if isinstance(storyboard_payload, Mapping) else None
        if isinstance(storyboard_shots, list):
            authoritative_shots = [serialize_shot_for_storage(shot) for shot in storyboard_shots]

    if prune_generated_files_to_shots and authoritative_shots:
        merged_generated_files = prune_generated_files_to_storyboard(
            merged_generated_files,
            authoritative_shots,
        )

    if invalidate_shot_ids:
        merged_generated_files = invalidate_generated_files_for_shots(
            merged_generated_files,
            authoritative_shots,
            invalidate_shot_ids,
            clear_videos_for_invalidated_shots=clear_videos_for_invalidated_shots,
            clear_final_video=clear_final_video,
        )
    elif clear_final_video:
        merged_generated_files.pop("final_video_url", None)

    if final_video_url is not None:
        merged_generated_files["final_video_url"] = final_video_url

    next_pipeline = {
        "status": existing_pipeline.get("status"),
        "progress": existing_pipeline.get("progress", 0),
        "current_step": existing_pipeline.get("current_step"),
        "error": existing_pipeline.get("error"),
        "progress_detail": existing_pipeline.get("progress_detail"),
        "generated_files": merged_generated_files,
    }

    if not next_pipeline["status"]:
        next_pipeline["status"] = PipelineStatus.PENDING
    if not next_pipeline["current_step"]:
        next_pipeline["current_step"] = "Manual asset persisted"

    await repo.save_pipeline(
        db,
        normalized_pipeline_id,
        normalized_story_id,
        next_pipeline,
    )
    return merged_generated_files
