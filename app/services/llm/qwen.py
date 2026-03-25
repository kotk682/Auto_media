from openai import AsyncOpenAI
from app.services.llm.base import BaseLLMProvider


class QwenProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", model: str = "qwen-plus"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        text, _ = await self.complete_with_usage(system, user, temperature)
        return text

    async def complete_with_usage(self, system: str, user: str, temperature: float = 0.3) -> tuple[str, dict]:
        return await self.complete_messages_with_usage(
            messages=[{"role": "user", "content": user}],
            system=system,
            temperature=temperature,
        )

    async def complete_messages_with_usage(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.3,
        enable_caching: bool = False,
        cache_key: str = "",
        cache_threshold_tokens: int = 1024,
    ) -> tuple[str, dict]:
        del enable_caching, cache_key, cache_threshold_tokens
        request_messages = [
            {"role": message.get("role", "user"), "content": message.get("content", "")}
            for message in messages
        ]
        if system:
            request_messages = [{"role": "system", "content": system}, *request_messages]

        stream = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            messages=request_messages,
            stream=True,
        )

        chunks: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)
            usage_obj = getattr(chunk, "usage", None)
            if usage_obj:
                prompt_tokens += getattr(usage_obj, "prompt_tokens", 0) or 0
                completion_tokens += getattr(usage_obj, "completion_tokens", 0) or 0

        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        return "".join(chunks), usage
