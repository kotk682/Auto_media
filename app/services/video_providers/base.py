from abc import ABC, abstractmethod


class BaseVideoProvider(ABC):
    """Abstract base for all video generation providers."""

    @abstractmethod
    async def generate(
        self,
        image_url: str,
        prompt: str,
        model: str,
        api_key: str,
        base_url: str,
    ) -> str:
        """
        Submit image-to-video task and wait for completion.

        Returns:
            Remote video URL (ready to download).
        """
        ...
