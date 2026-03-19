from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        """Send a prompt and return the text response."""
        ...
