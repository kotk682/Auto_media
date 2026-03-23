from app.services.video_providers.base import BaseVideoProvider


def get_video_provider(provider: str) -> BaseVideoProvider:
    """
    Return a video provider instance by name.

    Supported providers: dashscope (default), kling
    """
    name = (provider or "dashscope").lower()

    if name == "kling":
        from app.services.video_providers.kling import KlingVideoProvider
        return KlingVideoProvider()

    from app.services.video_providers.dashscope import DashScopeVideoProvider
    return DashScopeVideoProvider()
