"""
统一 API Key 提取与校验模块

优先级（以 LLM 为例）：
  前端 X-LLM-API-Key header → .env ANTHROPIC_API_KEY → 400 错误

使用方式：
  keys = extract_api_keys(request)
  image_cfg = resolve_image_config(keys.image_api_key, keys.image_base_url, keys.image_provider)
"""
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse, unquote

from fastapi import HTTPException, Request
from app.core.config import settings as _cfg

DEFAULT_ART_STYLE = "写实摄影风格，电影级画质，自然光影，高清细节，真实质感"


def _normalize_secret_like(value: str) -> str:
    return str(value or "").strip()


def _normalize_base_url(url: str) -> str:
    return _normalize_secret_like(url).rstrip("/").lower()


def _resolve_config_value(*attr_names: str) -> str:
    for attr_name in attr_names:
        value = _normalize_secret_like(getattr(_cfg, attr_name, ""))
        if value:
            return value
    return ""


def _resolve_default_provider(
    configured_value: str,
    provider_config: dict[str, dict[str, tuple[str, ...] | str]],
    *,
    fallback: str,
) -> str:
    normalized = _normalize_secret_like(configured_value).lower()
    if normalized in provider_config:
        return normalized
    return fallback


_IMAGE_PROVIDER_CONFIG: dict[str, dict[str, tuple[str, ...] | str]] = {
    "siliconflow": {
        "key_attrs": ("siliconflow_image_api_key", "siliconflow_api_key"),
        "base_url_attrs": ("siliconflow_image_base_url", "siliconflow_base_url"),
        "host_markers": ("siliconflow.cn",),
        "env_hint": "SILICONFLOW_IMAGE_API_KEY",
    },
    "doubao": {
        "key_attrs": ("doubao_image_api_key", "doubao_api_key"),
        "base_url_attrs": ("doubao_image_base_url", "doubao_base_url"),
        "host_markers": ("volces.com", "volcengine"),
        "env_hint": "DOUBAO_IMAGE_API_KEY",
    },
}

_VIDEO_PROVIDER_CONFIG: dict[str, dict[str, tuple[str, ...] | str]] = {
    "dashscope": {
        "key_attrs": ("dashscope_video_api_key", "dashscope_api_key"),
        "base_url_attrs": ("dashscope_video_base_url", "dashscope_base_url"),
        "host_markers": ("dashscope.aliyuncs.com",),
        "env_hint": "DASHSCOPE_VIDEO_API_KEY",
    },
    "kling": {
        "key_attrs": ("kling_video_api_key", "kling_api_key"),
        "base_url_attrs": ("kling_video_base_url", "kling_base_url"),
        "host_markers": ("klingai.com",),
        "env_hint": "KLING_VIDEO_API_KEY",
    },
    "minimax": {
        "key_attrs": ("minimax_video_api_key",),
        "base_url_attrs": ("minimax_video_base_url",),
        "host_markers": ("minimaxi.chat",),
        "env_hint": "MINIMAX_VIDEO_API_KEY",
    },
    "doubao": {
        "key_attrs": ("doubao_video_api_key", "doubao_api_key"),
        "base_url_attrs": ("doubao_video_base_url", "doubao_base_url"),
        "host_markers": ("volces.com", "volcengine"),
        "env_hint": "DOUBAO_VIDEO_API_KEY",
    },
}

_LLM_PROVIDER_HOST_MARKERS: dict[str, tuple[str, ...]] = {
    "claude": ("api.anthropic.com",),
    "openai": ("api.openai.com",),
    "qwen": ("dashscope.aliyuncs.com",),
    "zhipu": ("open.bigmodel.cn",),
    "gemini": ("generativelanguage.googleapis.com",),
    "siliconflow": ("siliconflow.cn",),
}


def _infer_provider_from_base_url(
    base_url: str,
    provider_config: dict[str, dict[str, tuple[str, ...] | str]],
    *,
    default_provider: str,
) -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return default_provider

    for provider, config in provider_config.items():
        configured_base_url = _normalize_base_url(_resolve_config_value(*config["base_url_attrs"]))
        if configured_base_url and normalized == configured_base_url:
            return provider

    for provider, config in provider_config.items():
        if any(marker in normalized for marker in config["host_markers"]):
            return provider

    return "custom"


def _is_known_provider_base_url(
    base_url: str,
    provider: str,
    provider_config: dict[str, dict[str, tuple[str, ...] | str]],
) -> bool:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return False

    config = provider_config.get(provider)
    if not config:
        return False

    configured_base_url = _normalize_base_url(_resolve_config_value(*config["base_url_attrs"]))
    if configured_base_url and normalized == configured_base_url:
        return True

    return any(marker in normalized for marker in config["host_markers"])


def _infer_llm_provider_from_base_url(base_url: str, default_provider: str) -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return default_provider

    for provider, (key_attr, url_attr) in _PROVIDER_CONFIG.items():
        configured_base_url = _normalize_base_url(_normalize_secret_like(getattr(_cfg, url_attr, "")))
        if configured_base_url and normalized == configured_base_url:
            return provider

    for provider, markers in _LLM_PROVIDER_HOST_MARKERS.items():
        if any(marker in normalized for marker in markers):
            return provider

    return default_provider


def _is_known_llm_provider_base_url(base_url: str, provider: str, url_attr: str) -> bool:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return False

    configured_base_url = _normalize_base_url(_normalize_secret_like(getattr(_cfg, url_attr, "")))
    if configured_base_url and normalized == configured_base_url:
        return True

    return any(marker in normalized for marker in _LLM_PROVIDER_HOST_MARKERS.get(provider, ()))


def infer_image_provider(base_url: str = "", provider: str = "") -> str:
    normalized_provider = _normalize_secret_like(provider).lower()
    if normalized_provider in _IMAGE_PROVIDER_CONFIG:
        return normalized_provider
    return _infer_provider_from_base_url(
        base_url,
        _IMAGE_PROVIDER_CONFIG,
        default_provider=get_default_image_provider(),
    )


def infer_video_provider(base_url: str = "", provider: str = "") -> str:
    normalized_provider = _normalize_secret_like(provider).lower()
    if normalized_provider in _VIDEO_PROVIDER_CONFIG:
        return normalized_provider
    return _infer_provider_from_base_url(
        base_url,
        _VIDEO_PROVIDER_CONFIG,
        default_provider=get_default_video_provider(),
    )


def _get_provider_api_key(
    provider: str,
    provider_config: dict[str, dict[str, tuple[str, ...] | str]],
) -> str:
    config = provider_config.get(provider)
    if not config:
        return ""
    return _resolve_config_value(*config["key_attrs"])


def _get_provider_base_url(
    provider: str,
    provider_config: dict[str, dict[str, tuple[str, ...] | str]],
) -> str:
    config = provider_config.get(provider)
    if not config:
        return ""
    return _resolve_config_value(*config["base_url_attrs"])


def _get_provider_env_hint(
    provider: str,
    provider_config: dict[str, dict[str, tuple[str, ...] | str]],
) -> str:
    config = provider_config.get(provider)
    if not config:
        return ""
    return str(config["env_hint"])


def get_image_provider_api_key(provider: str) -> str:
    normalized_provider = _normalize_secret_like(provider).lower() or "siliconflow"
    return _get_provider_api_key(normalized_provider, _IMAGE_PROVIDER_CONFIG)


def get_image_provider_base_url(provider: str) -> str:
    normalized_provider = _normalize_secret_like(provider).lower() or "siliconflow"
    return _get_provider_base_url(normalized_provider, _IMAGE_PROVIDER_CONFIG)


def get_default_image_provider() -> str:
    return _resolve_default_provider(
        getattr(_cfg, "default_image_provider", ""),
        _IMAGE_PROVIDER_CONFIG,
        fallback="siliconflow",
    )


def get_default_video_provider() -> str:
    return _resolve_default_provider(
        getattr(_cfg, "default_video_provider", ""),
        _VIDEO_PROVIDER_CONFIG,
        fallback="dashscope",
    )


@dataclass
class ApiKeyBundle:
    llm_api_key: str
    llm_base_url: str
    llm_provider: str
    llm_model: str
    image_api_key: str
    image_base_url: str
    image_provider: str
    video_api_key: str
    video_base_url: str
    video_provider: str


def extract_api_keys(request: Request) -> ApiKeyBundle:
    """从 HTTP Headers 统一提取所有 API Key 和 Base URL。"""
    return ApiKeyBundle(
        llm_api_key=_normalize_secret_like(request.headers.get("X-LLM-API-Key", "")),
        llm_base_url=_normalize_secret_like(request.headers.get("X-LLM-Base-URL", "")),
        llm_provider=_normalize_secret_like(request.headers.get("X-LLM-Provider", "")),
        llm_model=_normalize_secret_like(request.headers.get("X-LLM-Model", "")),
        image_api_key=_normalize_secret_like(request.headers.get("X-Image-API-Key", "")),
        image_base_url=_normalize_secret_like(request.headers.get("X-Image-Base-URL", "")),
        image_provider=_normalize_secret_like(request.headers.get("X-Image-Provider", "")),
        video_api_key=_normalize_secret_like(request.headers.get("X-Video-API-Key", "")),
        video_base_url=_normalize_secret_like(request.headers.get("X-Video-Base-URL", "")),
        video_provider=_normalize_secret_like(request.headers.get("X-Video-Provider", "")),
    )


def _missing_image_key_detail(provider: str) -> str:
    env_hint = _get_provider_env_hint(provider, _IMAGE_PROVIDER_CONFIG) or "对应图片服务商 Key"
    return (
        f"图片生成 API Key 未配置 (provider={provider})，"
        f"请在设置页填写，或在 .env 中配置 {env_hint}"
    )


def _missing_video_key_detail(provider: str) -> str:
    env_hint = _get_provider_env_hint(provider, _VIDEO_PROVIDER_CONFIG) or "对应视频服务商 Key"
    return (
        f"视频生成 API Key 未配置 (provider={provider})，"
        f"请在设置页填写，或在 .env 中配置 {env_hint}"
    )


def resolve_image_key(header_key: str, image_base_url: str = "", image_provider: str = "") -> str:
    """
    兼容旧调用：返回图片生成 API Key。

    真实链路请优先使用 resolve_image_config()，这样可以基于图片 Base URL
    自动判断是 SiliconFlow 还是豆包，并回退到对应图片配置。
    """
    return resolve_image_config(
        header_key=header_key,
        header_base_url=image_base_url,
        header_provider=image_provider,
    )["image_api_key"]


def resolve_image_config(header_key: str = "", header_base_url: str = "", header_provider: str = "") -> dict:
    """
    解析图片生成配置，优先级：
      provider : X-Image-Provider → 基于 X-Image-Base-URL 推断 → .env DEFAULT_IMAGE_PROVIDER
      api_key  : X-Image-API-Key  → .env <image-provider>_IMAGE_API_KEY → 400
      base_url : X-Image-Base-URL → .env <image-provider>_IMAGE_BASE_URL

    说明：
      - 浏览器未显式配置图片设置时，可仅通过 .env DEFAULT_IMAGE_PROVIDER 选择默认图片服务商。
      - 若 base_url 命中已知图片服务商（SiliconFlow / Doubao），允许继续回退到对应 .env Key。
      - 若是未知自定义 base_url，则必须同时提供 X-Image-API-Key。
    """
    normalized_key = _normalize_secret_like(header_key)
    normalized_provider = _normalize_secret_like(header_provider).lower()
    validated_base_url = validate_user_base_url(_normalize_secret_like(header_base_url))
    if normalized_provider and normalized_provider not in _IMAGE_PROVIDER_CONFIG and normalized_provider != "custom":
        supported = ", ".join(list(_IMAGE_PROVIDER_CONFIG) + ["custom"])
        raise HTTPException(status_code=400, detail=f"不支持的图片服务商: {normalized_provider}，可选值: {supported}")
    provider = normalized_provider or infer_image_provider(validated_base_url)

    if provider == "custom":
        if not normalized_key or not validated_base_url:
            raise HTTPException(
                status_code=400,
                detail="使用自定义图片服务商时必须同时提供 X-Image-Base-URL 和 X-Image-API-Key",
            )
        return {
            "image_api_key": normalized_key,
            "image_base_url": validated_base_url,
            "image_provider": provider,
        }

    resolved_provider = provider
    api_key = normalized_key or get_image_provider_api_key(resolved_provider)
    if not api_key:
        raise HTTPException(status_code=400, detail=_missing_image_key_detail(resolved_provider))

    base_url = validated_base_url or get_image_provider_base_url(resolved_provider)
    return {
        "image_api_key": api_key,
        "image_base_url": base_url,
        "image_provider": resolved_provider,
    }



def validate_user_base_url(url: str) -> str:
    """
    验证用户提供的 base URL，防止 SSRF 攻击。

    规则（始终执行）：
    - 空字符串直接放行（调用方回退到默认值）
    - 必须使用 https 协议
    - 若 hostname 本身是 IP 字面量，拒绝 loopback / 私有 / link-local

    规则（仅 VALIDATE_BASE_URL_DNS=true 时执行）：
    - 对域名做 DNS 解析，拒绝解析结果为内网 IP 的地址
    - 生产环境建议开启；国内开发环境可保持默认 false（境外域名可能无法解析）

    不做 host 白名单：本项目支持任意第三方 API 供应商。
    """
    if not url:
        return url

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="base_url 必须使用 https 协议")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="base_url 缺少有效的主机名")

    # 始终检查：hostname 本身是 IP 字面量时拒绝内网地址
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback or ip.is_private or ip.is_link_local:
            raise HTTPException(status_code=400, detail="base_url 不允许指向内网或本地地址")
        return url  # 合法公网 IP，无需再做 DNS 解析
    except ValueError:
        pass  # 普通域名，继续走 DNS 检查逻辑

    # 可选检查：DNS 解析后验证结果 IP
    if _cfg.validate_base_url_dns:
        try:
            infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            raise HTTPException(status_code=400, detail=f"base_url 主机名无法解析: {hostname}")
        for info in infos:
            ip_str = info[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if ip.is_loopback or ip.is_private or ip.is_link_local:
                raise HTTPException(status_code=400, detail="base_url 不允许指向内网或本地地址")

    return url


def mask_key(key: str) -> str:
    """脱敏 API Key，用于日志和错误信息输出，避免明文泄露。"""
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


# ── FastAPI Depends 依赖函数 ──────────────────────────────────────────────────
# 用于 router 函数签名，消除每个 endpoint 重复的两行 extract + resolve 样板代码。
# FastAPI 自动将 request: Request 注入，HTTPException 在此处抛出与在 endpoint 中等价。

# provider 名称 → (api_key 字段名, base_url 字段名)
# "claude" 对应 config 里的 anthropic_* 字段
_PROVIDER_CONFIG: dict[str, tuple[str, str]] = {
    "claude": ("anthropic_api_key", "anthropic_base_url"),
    "openai": ("openai_api_key",    "openai_base_url"),
    "qwen":   ("qwen_api_key",      "qwen_base_url"),
    "zhipu":  ("zhipu_api_key",     "zhipu_base_url"),
    "gemini":      ("gemini_api_key",      "gemini_base_url"),
    "siliconflow": ("siliconflow_api_key", "siliconflow_base_url"),
}


def resolve_llm_config(header_key: str, header_base_url: str, header_provider: str, header_model: str = "") -> dict:
    """
    解析 LLM 配置，优先级：
      api_key  : Header X-LLM-API-Key  → .env <provider>_API_KEY
      base_url : Header X-LLM-Base-URL → .env <provider>_BASE_URL
      provider : Header X-LLM-Provider → settings.default_llm_provider
      model    : Header X-LLM-Model    → "" (后端用 MODEL_MAP 默认值)

    安全规则：
      - 若客户端提供 base_url，则必须同时提供 api_key，不使用服务端 key。
      - 未知/自定义 provider 必须同时提供 api_key 和 base_url，不回退 anthropic 凭证。
    """
    header_key = _normalize_secret_like(header_key)
    header_base_url = _normalize_secret_like(header_base_url)
    header_provider = _normalize_secret_like(header_provider)
    header_model = _normalize_secret_like(header_model)

    validated_base_url = validate_user_base_url(header_base_url)
    default_provider = _normalize_secret_like(_cfg.default_llm_provider)
    provider = header_provider or _infer_llm_provider_from_base_url(validated_base_url, default_provider) or default_provider

    if provider not in _PROVIDER_CONFIG:
        # 未知/自定义服务商：必须客户端自行提供全部凭证
        if not header_key or not validated_base_url:
            raise HTTPException(
                status_code=400,
                detail=f"自定义服务商 '{provider}' 必须同时提供 X-LLM-API-Key 和 X-LLM-Base-URL",
            )
        return {"api_key": header_key, "base_url": validated_base_url, "provider": provider, "model": header_model}

    key_attr, url_attr = _PROVIDER_CONFIG[provider]

    if validated_base_url:
        # 已知 provider 的默认/官方 base_url 允许继续回退服务端凭证；
        # 未知自定义 base_url 则必须同时提供 key。
        if not header_key and not _is_known_llm_provider_base_url(validated_base_url, provider, url_attr):
            raise HTTPException(
                status_code=400,
                detail="使用自定义 X-LLM-Base-URL 时必须同时提供 X-LLM-API-Key",
            )
        api_key = header_key or _normalize_secret_like(getattr(_cfg, key_attr, ""))
        if not api_key and not _cfg.debug:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"LLM API Key 未配置 (provider={provider})，"
                    "请在前端设置中填写，或在后端 .env 中配置对应密钥"
                ),
            )
        return {"api_key": api_key, "base_url": validated_base_url, "provider": provider, "model": header_model}

    # 未提供自定义 base_url：正常回退到服务端配置
    api_key = header_key or _normalize_secret_like(getattr(_cfg, key_attr, ""))
    base_url = _normalize_secret_like(getattr(_cfg, url_attr, ""))
    if not api_key and not _cfg.debug:
        raise HTTPException(
            status_code=400,
            detail=(
                f"LLM API Key 未配置 (provider={provider})，"
                "请在前端设置中填写，或在后端 .env 中配置对应密钥"
            ),
        )
    return {"api_key": api_key, "base_url": base_url, "provider": provider, "model": header_model}


def image_config_dep(request: Request) -> dict:
    """Depends：提取图片生成配置（api_key / base_url），返回 dict 供 ** 解构。"""
    keys = extract_api_keys(request)
    return resolve_image_config(keys.image_api_key, keys.image_base_url, keys.image_provider)




def video_config_dep(request: Request) -> dict:
    """Depends：提取视频生成配置（api_key / base_url / provider），返回 dict 供 ** 解构。"""
    keys = extract_api_keys(request)
    return resolve_video_config(keys.video_api_key, keys.video_base_url, keys.video_provider)


def resolve_video_config(header_key: str = "", header_base_url: str = "", header_provider: str = "") -> dict:
    """
    解析视频生成配置，优先级：
      provider : X-Video-Provider → 基于 X-Video-Base-URL 推断 → .env DEFAULT_VIDEO_PROVIDER
      api_key  : X-Video-API-Key  → .env <video-provider>_VIDEO_API_KEY → 400
      base_url : X-Video-Base-URL → .env <video-provider>_VIDEO_BASE_URL

    规则：
      - 已知 provider（DashScope / Kling / MiniMax / Doubao）即使传了默认 base_url，
        也允许继续回退到对应 .env 的视频 Key。
      - 未知/自定义 provider 暂不支持服务端统一适配。
    """
    normalized_key = _normalize_secret_like(header_key)
    normalized_provider = _normalize_secret_like(header_provider).lower()
    validated_base_url = validate_user_base_url(_normalize_secret_like(header_base_url))
    inferred_provider = infer_video_provider(validated_base_url, normalized_provider)
    video_provider = normalized_provider or inferred_provider or get_default_video_provider()

    if video_provider not in _VIDEO_PROVIDER_CONFIG:
        supported = ", ".join(_VIDEO_PROVIDER_CONFIG)
        raise HTTPException(status_code=400, detail=f"不支持的视频服务商: {video_provider}，可选值: {supported}")

    if validated_base_url and not _is_known_provider_base_url(validated_base_url, video_provider, _VIDEO_PROVIDER_CONFIG) and not normalized_key:
        raise HTTPException(
            status_code=400,
            detail="使用自定义 X-Video-Base-URL 时必须同时提供 X-Video-API-Key",
        )

    api_key = normalized_key or _get_provider_api_key(video_provider, _VIDEO_PROVIDER_CONFIG)
    if not api_key:
        raise HTTPException(status_code=400, detail=_missing_video_key_detail(video_provider))

    base_url = validated_base_url or _get_provider_base_url(video_provider, _VIDEO_PROVIDER_CONFIG)
    return {
        "video_api_key": api_key,
        "video_base_url": base_url,
        "video_provider": video_provider,
    }


def llm_config_dep(request: Request) -> dict:
    """Depends：提取 LLM 配置（api_key / base_url / provider），返回 dict 供 ** 解构。"""
    keys = extract_api_keys(request)
    return resolve_llm_config(keys.llm_api_key, keys.llm_base_url, keys.llm_provider, keys.llm_model)


def get_art_style(request: Request) -> str:
    """从 X-Art-Style Header 读取并 URL 解码画风提示词。"""
    raw = request.headers.get("X-Art-Style", "")
    normalized = unquote(raw).strip()
    return normalized or DEFAULT_ART_STYLE


def inject_art_style(prompt: str, art_style: str) -> str:
    """Append art style to end of prompt (content first, style weight second)."""
    if not art_style or not prompt:
        return prompt
    normalized_prompt = prompt.rstrip()
    normalized_style = art_style.strip()
    if not normalized_style:
        return normalized_prompt
    if normalized_prompt.endswith(normalized_style):
        return normalized_prompt
    if f", {normalized_style}" in normalized_prompt:
        return normalized_prompt
    return f"{normalized_prompt}, {normalized_style}"
