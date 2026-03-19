from app.services.llm.base import BaseLLMProvider
from app.core.config import settings

PROVIDER_MODELS = {
    "claude": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "qwen":   ["qwen-plus", "qwen-max", "qwen-turbo"],
    "zhipu":  ["glm-4", "glm-4-flash", "glm-3-turbo"],
    "gemini": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-flash"],
}


def get_llm_provider(provider: str, model: str | None = None) -> BaseLLMProvider:
    name = provider.lower()
    resolved_model = model or PROVIDER_MODELS[name][0]

    if name == "claude":
        from app.services.llm.claude import ClaudeProvider
        return ClaudeProvider(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url, model=resolved_model)

    if name == "openai":
        from app.services.llm.openai import OpenAIProvider
        return OpenAIProvider(api_key=settings.openai_api_key, base_url=settings.openai_base_url, model=resolved_model)

    if name == "qwen":
        from app.services.llm.qwen import QwenProvider
        return QwenProvider(api_key=settings.qwen_api_key, base_url=settings.qwen_base_url, model=resolved_model)

    if name == "zhipu":
        from app.services.llm.zhipu import ZhipuProvider
        return ZhipuProvider(api_key=settings.zhipu_api_key, base_url=settings.zhipu_base_url, model=resolved_model)

    if name == "gemini":
        from app.services.llm.gemini import GeminiProvider
        return GeminiProvider(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url, model=resolved_model)

    raise ValueError(f"Unknown LLM provider: {name}")
