import logging

from openai import AsyncOpenAI
from app.services.llm.base import BaseLLMProvider
from app.services.llm.telemetry import LLMCallTracker, estimate_request_chars


logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    provider_name = "gemini"

    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/", model: str = "gemini-1.5-pro"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def complete(self, system: str, user: str, temperature: float = 0.3, telemetry_context=None) -> str:
        tracker = LLMCallTracker(
            provider=self.provider_name,
            model=self._model,
            request_chars=estimate_request_chars(system=system, user=user),
            context=telemetry_context,
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            tracker.record_failure(exc)
            raise
        text = resp.choices[0].message.content
        tracker.record_success(usage=getattr(resp, "usage", None), response_text=text)
        return text

    async def complete_with_usage(self, system: str, user: str, temperature: float = 0.3, telemetry_context=None) -> tuple[str, dict]:
        tracker = LLMCallTracker(
            provider=self.provider_name,
            model=self._model,
            request_chars=estimate_request_chars(system=system, user=user),
            context=telemetry_context,
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            tracker.record_failure(exc)
            raise
        usage_obj = getattr(resp, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.prompt_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.completion_tokens if usage_obj else 0,
        }
        text = resp.choices[0].message.content
        tracker.record_success(usage=usage, response_text=text)
        return text, usage

    async def complete_messages_with_usage(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.3,
        enable_caching: bool = False,
        cache_key: str = "",
        cache_threshold_tokens: int = 1024,
        telemetry_context=None,
    ) -> tuple[str, dict]:
        if not messages:
            raise ValueError(
                "GeminiProvider.complete_messages_with_usage requires at least one message; "
                "refusing to call the Gemini API with an empty user prompt."
            )
        if enable_caching:
            logger.debug(
                "GeminiProvider does not support prompt caching; ignoring enable_caching=%s cache_key=%r cache_threshold_tokens=%s",
                enable_caching,
                cache_key,
                cache_threshold_tokens,
            )
        request_messages = [
            {"role": message.get("role", "user"), "content": message.get("content", "")}
            for message in messages
        ]
        if system:
            request_messages = [{"role": "system", "content": system}, *request_messages]
        tracker = LLMCallTracker(
            provider=self.provider_name,
            model=self._model,
            request_chars=estimate_request_chars(system=system, messages=messages),
            context=telemetry_context,
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                messages=request_messages,
            )
        except Exception as exc:
            tracker.record_failure(exc)
            raise
        usage_obj = getattr(resp, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.prompt_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.completion_tokens if usage_obj else 0,
        }
        text = resp.choices[0].message.content
        tracker.record_success(usage=usage, response_text=text)
        return text, usage
