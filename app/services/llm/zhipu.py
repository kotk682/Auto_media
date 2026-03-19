from openai import AsyncOpenAI
from app.services.llm.base import BaseLLMProvider


class ZhipuProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://open.bigmodel.cn/api/paas/v4/", model: str = "glm-4"):
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
