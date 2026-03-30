from fastapi import HTTPException

from app.core.config import settings


DEFAULT_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"
DEFAULT_DASHSCOPE_VIDEO_MODEL = "wan2.6-i2v-flash"
DEFAULT_KLING_VIDEO_MODEL = "kling-v2-master"
DEFAULT_MINIMAX_VIDEO_MODEL = "video-01"


def _normalize(value: str) -> str:
    return str(value or "").strip()


def _normalize_doubao_endpoint_model(value: str) -> str:
    normalized = _normalize(value)
    while normalized.startswith("ep-ep-"):
        normalized = normalized[3:]
    return normalized


def _normalize_base_url(url: str) -> str:
    return _normalize(url).rstrip("/").lower()


def _configured_base_urls(*urls: str) -> set[str]:
    return {
        normalized
        for normalized in (_normalize_base_url(url) for url in urls)
        if normalized
    }


def _is_doubao_base_url(url: str) -> bool:
    normalized = _normalize_base_url(url)
    return (
        normalized in _configured_base_urls(
            settings.doubao_image_base_url,
            settings.doubao_video_base_url,
            settings.doubao_base_url,
        )
        or "volces.com" in normalized
        or "volcengine" in normalized
    )


def _is_siliconflow_base_url(url: str) -> bool:
    normalized = _normalize_base_url(url)
    return normalized in _configured_base_urls(
        settings.siliconflow_image_base_url,
        settings.siliconflow_base_url,
    ) or "siliconflow.cn" in normalized


def resolve_image_model(requested_model: str = "", image_base_url: str = "") -> str:
    normalized_base_url = _normalize(image_base_url) or _normalize(settings.siliconflow_image_base_url or settings.siliconflow_base_url)
    if _is_doubao_base_url(normalized_base_url):
        normalized_model = _normalize_doubao_endpoint_model(requested_model)
        if normalized_model:
            return normalized_model

        doubao_model = _normalize_doubao_endpoint_model(settings.doubao_image_model)
        if not doubao_model:
            raise HTTPException(
                status_code=400,
                detail=(
                    "当前图片服务商为豆包 / 火山方舟，必须提供模型端点 ID（ep-...）。"
                    "请在前端图片模型中填写，或在 .env 中配置 DOUBAO_IMAGE_MODEL"
                ),
        )
        return doubao_model

    normalized_model = _normalize(requested_model)
    if normalized_model:
        return normalized_model

    if _is_siliconflow_base_url(normalized_base_url):
        return _normalize(settings.siliconflow_image_model) or DEFAULT_IMAGE_MODEL

    return _normalize(settings.default_image_model) or DEFAULT_IMAGE_MODEL


def resolve_video_model(requested_model: str = "", video_provider: str = "") -> str:
    provider = _normalize(video_provider).lower() or "dashscope"
    if provider == "doubao":
        normalized_model = _normalize_doubao_endpoint_model(requested_model)
        if normalized_model:
            return normalized_model

        doubao_model = _normalize_doubao_endpoint_model(settings.doubao_video_model)
        if not doubao_model:
            raise HTTPException(
                status_code=400,
                detail=(
                    "当前视频服务商为豆包 / 火山方舟，必须提供模型端点 ID（ep-...）。"
                    "请在前端视频模型中填写，或在 .env 中配置 DOUBAO_VIDEO_MODEL"
                ),
            )
        return doubao_model

    normalized_model = _normalize(requested_model)
    if normalized_model:
        return normalized_model

    if provider == "kling":
        return _normalize(settings.kling_video_model) or DEFAULT_KLING_VIDEO_MODEL
    if provider == "minimax":
        return _normalize(settings.minimax_video_model) or DEFAULT_MINIMAX_VIDEO_MODEL
    if provider == "dashscope":
        return _normalize(settings.dashscope_video_model) or DEFAULT_DASHSCOPE_VIDEO_MODEL
    return _normalize(settings.default_video_model) or DEFAULT_DASHSCOPE_VIDEO_MODEL
