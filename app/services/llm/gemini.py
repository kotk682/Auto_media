import logging

from openai import AsyncOpenAI
from app.services.llm.base import BaseLLMProvider


logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/", model: str = "gemini-1.5-pro"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content

    async def complete_with_usage(self, system: str, user: str, temperature: float = 0.3) -> tuple[str, dict]:
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        usage_obj = getattr(resp, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.prompt_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.completion_tokens if usage_obj else 0,
        }
        return resp.choices[0].message.content, usage

    async def complete_messages_with_usage(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.3,
        enable_caching: bool = False,
        cache_key: str = "",
        cache_threshold_tokens: int = 1024,
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
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            messages=request_messages,
        )
        usage_obj = getattr(resp, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.prompt_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.completion_tokens if usage_obj else 0,
        }
        return resp.choices[0].message.content, usage
