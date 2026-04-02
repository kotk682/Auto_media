from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)


def _coerce_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _message_text(message: Mapping[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, Mapping) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
            else:
                chunks.append(str(item))
        return "\n".join(chunk for chunk in chunks if chunk)
    return str(content)


def estimate_request_chars(
    *,
    system: str = "",
    user: str = "",
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> int:
    total = len(str(system or ""))
    if messages is not None:
        total += sum(len(_message_text(message)) for message in messages)
        return total
    return total + len(str(user or ""))


def normalize_usage(usage: Any) -> dict[str, Any]:
    if isinstance(usage, Mapping):
        normalized = {
            "prompt_tokens": _coerce_int(usage.get("prompt_tokens", usage.get("input_tokens", 0))),
            "completion_tokens": _coerce_int(usage.get("completion_tokens", usage.get("output_tokens", 0))),
        }
        if "cache_enabled" in usage:
            normalized["cache_enabled"] = bool(usage.get("cache_enabled"))
        return normalized

    normalized = {
        "prompt_tokens": _coerce_int(getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", 0))),
        "completion_tokens": _coerce_int(
            getattr(usage, "completion_tokens", getattr(usage, "output_tokens", 0))
        ),
    }
    cache_enabled = getattr(usage, "cache_enabled", None)
    if cache_enabled is not None:
        normalized["cache_enabled"] = bool(cache_enabled)
    return normalized


def _normalize_context_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text:
        return None
    return text[:160]


def _format_fields(fields: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key, value in fields.items():
        normalized = _normalize_context_value(value)
        if normalized is None:
            continue
        if isinstance(normalized, bool):
            serialized = "true" if normalized else "false"
        elif isinstance(normalized, (int, float)):
            serialized = str(normalized)
        else:
            serialized = json.dumps(normalized, ensure_ascii=False)
        parts.append(f"{key}={serialized}")
    return " ".join(parts)


class LLMCallTracker:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        request_chars: int,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.provider = str(provider or "").strip() or "unknown"
        self.model = str(model or "").strip() or "(default)"
        self.request_chars = _coerce_int(request_chars)
        self.context = dict(context or {})
        self._started_at = time.perf_counter()
        self._first_token_at: float | None = None

    def mark_first_token(self) -> None:
        if settings.llm_telemetry_enabled and self._first_token_at is None:
            # Streaming requests care about first-token latency more than connect latency.
            self._first_token_at = time.perf_counter()

    def record_success(
        self,
        *,
        usage: Any = None,
        response_text: Any = "",
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        self._record(success=True, usage=usage, response_text=response_text, extra=extra)

    def record_failure(
        self,
        error: Exception,
        *,
        usage: Any = None,
        response_text: Any = "",
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        self._record(
            success=False,
            usage=usage,
            response_text=response_text,
            error=error,
            extra=extra,
        )

    def _record(
        self,
        *,
        success: bool,
        usage: Any = None,
        response_text: Any = "",
        error: Exception | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        if not settings.llm_telemetry_enabled:
            return

        merged_context = {**self.context, **dict(extra or {})}
        operation = str(merged_context.pop("operation", "")).strip() or "llm.call"
        usage_info = normalize_usage(usage)
        latency_ms = round((time.perf_counter() - self._started_at) * 1000)
        fields: dict[str, Any] = {
            "operation": operation,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": latency_ms,
            "prompt_tokens": usage_info.get("prompt_tokens", 0),
            "completion_tokens": usage_info.get("completion_tokens", 0),
            "request_chars": self.request_chars,
            "response_chars": len(str(response_text or "")),
            "success": success,
        }
        if self._first_token_at is not None:
            fields["first_token_ms"] = round((self._first_token_at - self._started_at) * 1000)
        if "cache_enabled" in usage_info:
            fields["cache_enabled"] = usage_info["cache_enabled"]
        if error is not None:
            fields["error_type"] = type(error).__name__
        for key, value in merged_context.items():
            fields[key] = value

        if success:
            is_slow_call = latency_ms >= settings.llm_slow_log_threshold_ms
            formatted_fields = _format_fields(fields)
            if is_slow_call:
                # Promote slow-call context to WARNING so warning-only log sinks can still pair
                # each LLM_SLOW line with the corresponding full LLM_CALL payload.
                logger.warning("LLM_CALL %s", formatted_fields)
                logger.warning(
                    "LLM_SLOW %s",
                    _format_fields(
                        {
                            "operation": operation,
                            "provider": self.provider,
                            "model": self.model,
                            "latency_ms": latency_ms,
                            "threshold_ms": settings.llm_slow_log_threshold_ms,
                            **merged_context,
                        }
                    ),
                )
                return
            logger.info("LLM_CALL %s", formatted_fields)
            return

        logger.warning("LLM_CALL %s", _format_fields(fields))
