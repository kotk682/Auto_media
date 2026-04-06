from openai import AsyncOpenAI
from app.services.llm.base import BaseLLMProvider, build_message_blocks, estimate_cacheable_prefix_tokens
from app.services.llm.telemetry import LLMCallTracker, estimate_request_chars, normalize_usage


class QwenProvider(BaseLLMProvider):
    provider_name = "qwen"

    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", model: str = "qwen-plus"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._base_url = base_url
        self._model = model

    async def complete(self, system: str, user: str, temperature: float = 0.3, telemetry_context=None) -> str:
        text, _ = await self.complete_with_usage(
            system,
            user,
            temperature,
            telemetry_context=telemetry_context,
        )
        return text

    async def complete_with_usage(self, system: str, user: str, temperature: float = 0.3, telemetry_context=None) -> tuple[str, dict]:
        return await self.complete_messages_with_usage(
            messages=[{"role": "user", "content": user}],
            system=system,
            temperature=temperature,
            telemetry_context=telemetry_context,
        )

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
        del cache_key
        stable_token_budget = estimate_cacheable_prefix_tokens(system=system, messages=messages)
        use_caching = enable_caching and stable_token_budget >= cache_threshold_tokens
        supports_dashscope_cache = "dashscope" in str(self._base_url or "")
        has_cacheable_message = any(bool(message.get("cacheable")) for message in messages)
        request_cache_enabled = use_caching and supports_dashscope_cache and has_cacheable_message

        request_messages = []
        for message in messages:
            content = message.get("content", "")
            if request_cache_enabled and bool(message.get("cacheable")):
                content = build_message_blocks(content, cacheable=True)
            request_messages.append(
                {"role": message.get("role", "user"), "content": content}
            )
        if system:
            request_messages = [{"role": "system", "content": system}, *request_messages]

        tracker = LLMCallTracker(
            provider=self.provider_name,
            model=self._model,
            request_chars=estimate_request_chars(system=system, messages=messages),
            context=telemetry_context,
        )
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                messages=request_messages,
                stream=True,
                stream_options={"include_usage": True},
            )
        except Exception as exc:
            tracker.record_failure(exc)
            raise

        chunks: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        last_usage_obj = None
        try:
            async for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if choices:
                    delta = getattr(choices[0].delta, "content", None)
                    if delta:
                        tracker.mark_first_token()
                        chunks.append(delta)
                usage_obj = getattr(chunk, "usage", None)
                if usage_obj:
                    last_usage_obj = usage_obj
                    prompt_tokens += getattr(usage_obj, "prompt_tokens", 0) or 0
                    completion_tokens += getattr(usage_obj, "completion_tokens", 0) or 0
        except Exception as exc:
            tracker.record_failure(
                exc,
                usage={
                    **normalize_usage(last_usage_obj),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cache_enabled": request_cache_enabled,
                },
                response_text="".join(chunks),
            )
            raise

        usage = normalize_usage(last_usage_obj)
        usage["prompt_tokens"] = prompt_tokens
        usage["completion_tokens"] = completion_tokens
        if request_cache_enabled:
            usage["cache_enabled"] = True
        text = "".join(chunks)
        tracker.record_success(usage=usage, response_text=text)
        return text, usage
