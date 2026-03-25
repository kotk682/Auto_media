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
        last_frame_url: str = "",
        negative_prompt: str = "",
    ) -> str:
        """
        Submit image-to-video task and wait for completion.

        Args:
            image_url: 首帧图片URL
            prompt: 动作描述
            model: 模型名称
            api_key: API密钥
            base_url: API基础URL
            last_frame_url: 尾帧图片URL（可选），提供时启用双帧过渡模式

        Returns:
            Remote video URL (ready to download).
        """
        ...
