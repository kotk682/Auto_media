from openai import AsyncOpenAI
from app.services.llm.base import BaseLLMProvider, build_cache_routing_key, estimate_cacheable_prefix_tokens
from app.services.llm.telemetry import LLMCallTracker, estimate_request_chars, normalize_usage


class OpenAIProvider(BaseLLMProvider):
    provider_name = "openai"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._base_url = base_url
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
        usage = normalize_usage(usage_obj)
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
        request_messages = [
            {"role": message.get("role", "user"), "content": message.get("content", "")}
            for message in messages
        ]
        if system:
            request_messages = [{"role": "system", "content": system}, *request_messages]
        stable_token_budget = estimate_cacheable_prefix_tokens(system=system, messages=messages)
        use_caching = enable_caching and stable_token_budget >= cache_threshold_tokens
        prompt_cache_key = ""
        extra_body = None
        if use_caching and "api.openai.com" in str(self._base_url or ""):
            prompt_cache_key = build_cache_routing_key(
                provider=self.provider_name,
                model=self._model,
                system=system,
                messages=messages,
                cache_key=cache_key,
            )
            if prompt_cache_key:
                extra_body = {"prompt_cache_key": prompt_cache_key}
        cache_enabled = bool(prompt_cache_key and extra_body and extra_body.get("prompt_cache_key"))
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
                extra_body=extra_body,
            )
        except Exception as exc:
            tracker.record_failure(exc, extra={"cache_enabled": cache_enabled})
            raise
        usage_obj = getattr(resp, "usage", None)
        usage = normalize_usage(usage_obj)
        if cache_enabled:
            usage["cache_enabled"] = True
        text = resp.choices[0].message.content
        tracker.record_success(usage=usage, response_text=text)
        return text, usage
