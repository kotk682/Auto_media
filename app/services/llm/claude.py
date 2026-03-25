import anthropic
from app.services.llm.base import BaseLLMProvider, estimate_tokens

class ClaudeProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com", model: str = "claude-sonnet-4-6"):
        self._client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
        self._model = model

    async def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text

    async def complete_with_usage(self, system: str, user: str, temperature: float = 0.3) -> tuple[str, dict]:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        usage_obj = getattr(msg, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.input_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.output_tokens if usage_obj else 0,
        }
        return msg.content[0].text, usage

    @staticmethod
    def _message_blocks(content, *, cacheable: bool = False) -> list[dict]:
        if isinstance(content, list):
            blocks = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    block = {"type": "text", "text": str(item.get("text", ""))}
                    if cacheable and block["text"]:
                        block["cache_control"] = {"type": "ephemeral"}
                    blocks.append(block)
                else:
                    text = str(item)
                    block = {"type": "text", "text": text}
                    if cacheable and text:
                        block["cache_control"] = {"type": "ephemeral"}
                    blocks.append(block)
            return blocks

        text = str(content or "")
        block = {"type": "text", "text": text}
        if cacheable and text:
            block["cache_control"] = {"type": "ephemeral"}
        return [block]

    async def complete_messages_with_usage(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.3,
        enable_caching: bool = False,
        _cache_key: str = "",
        cache_threshold_tokens: int = 1024,
    ) -> tuple[str, dict]:
        stable_token_budget = sum(
            estimate_tokens(message)
            for message in messages
            if message.get("cacheable")
        )
        use_caching = enable_caching and stable_token_budget >= cache_threshold_tokens

        request_messages = []
        for message in messages:
            request_messages.append(
                {
                    "role": message.get("role", "user"),
                    "content": self._message_blocks(
                        message.get("content", ""),
                        cacheable=use_caching and bool(message.get("cacheable")),
                    ),
                }
            )

        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=request_messages,
        )
        usage_obj = getattr(msg, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.input_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.output_tokens if usage_obj else 0,
            "cache_enabled": use_caching,
        }
        return msg.content[0].text, usage
