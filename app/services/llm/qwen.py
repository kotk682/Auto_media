from openai import AsyncOpenAI
from app.services.llm.base import BaseLLMProvider
from app.services.llm.telemetry import LLMCallTracker, estimate_request_chars


class QwenProvider(BaseLLMProvider):
    provider_name = "qwen"

    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", model: str = "qwen-plus"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
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
        del enable_caching, cache_key, cache_threshold_tokens
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
                    prompt_tokens += getattr(usage_obj, "prompt_tokens", 0) or 0
                    completion_tokens += getattr(usage_obj, "completion_tokens", 0) or 0
        except Exception as exc:
            tracker.record_failure(
                exc,
                usage={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
                response_text="".join(chunks),
            )
            raise

        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        text = "".join(chunks)
        tracker.record_success(usage=usage, response_text=text)
        return text, usage
