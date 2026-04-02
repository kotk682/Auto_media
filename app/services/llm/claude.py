import anthropic
from app.services.llm.base import BaseLLMProvider, estimate_tokens
from app.services.llm.telemetry import LLMCallTracker, estimate_request_chars

class ClaudeProvider(BaseLLMProvider):
    provider_name = "claude"

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com", model: str = "claude-sonnet-4-6"):
        self._client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
        self._model = model

    async def complete(self, system: str, user: str, temperature: float = 0.3, telemetry_context=None) -> str:
        tracker = LLMCallTracker(
            provider=self.provider_name,
            model=self._model,
            request_chars=estimate_request_chars(system=system, user=user),
            context=telemetry_context,
        )
        try:
            msg = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            tracker.record_failure(exc)
            raise
        text = msg.content[0].text
        tracker.record_success(usage=getattr(msg, "usage", None), response_text=text)
        return text

    async def complete_with_usage(self, system: str, user: str, temperature: float = 0.3, telemetry_context=None) -> tuple[str, dict]:
        tracker = LLMCallTracker(
            provider=self.provider_name,
            model=self._model,
            request_chars=estimate_request_chars(system=system, user=user),
            context=telemetry_context,
        )
        try:
            msg = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            tracker.record_failure(exc)
            raise
        usage_obj = getattr(msg, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.input_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.output_tokens if usage_obj else 0,
        }
        text = msg.content[0].text
        tracker.record_success(usage=usage, response_text=text)
        return text, usage

    @staticmethod
    def _message_blocks(content, *, cacheable: bool = False) -> list[dict]:
        if isinstance(content, list):
            blocks = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        block = {"type": "text", "text": str(item.get("text", ""))}
                        if cacheable and block["text"]:
                            block["cache_control"] = {"type": "ephemeral"}
                        blocks.append(block)
                    else:
                        blocks.append(item)
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
        cache_key: str = "",
        cache_threshold_tokens: int = 1024,
        telemetry_context=None,
    ) -> tuple[str, dict]:
        del cache_key
        stable_token_budget = 0
        if system:
            stable_token_budget += estimate_tokens({"role": "system", "content": system})
        for message in messages:
            stable_token_budget += estimate_tokens(message)
            if message.get("cacheable"):
                break
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

        tracker = LLMCallTracker(
            provider=self.provider_name,
            model=self._model,
            request_chars=estimate_request_chars(system=system, messages=messages),
            context=telemetry_context,
        )
        try:
            msg = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                temperature=temperature,
                system=system,
                messages=request_messages,
            )
        except Exception as exc:
            tracker.record_failure(exc, extra={"cache_enabled": use_caching})
            raise
        usage_obj = getattr(msg, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.input_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.output_tokens if usage_obj else 0,
            "cache_enabled": use_caching,
        }
        text = msg.content[0].text
        tracker.record_success(usage=usage, response_text=text)
        return text, usage
