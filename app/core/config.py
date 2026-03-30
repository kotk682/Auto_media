from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AutoMedia API"
    database_url: str = "sqlite+aiosqlite:///./automedia.db"
    debug: bool = True

    # LLM
    default_llm_provider: str = "claude"
    default_image_provider: str = "siliconflow"
    default_video_provider: str = "dashscope"

    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Image generation
    default_image_model: str = "black-forest-labs/FLUX.1-schnell"
    siliconflow_image_api_key: str = ""
    siliconflow_image_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_image_model: str = "black-forest-labs/FLUX.1-schnell"
    doubao_image_api_key: str = ""
    doubao_image_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_image_model: str = ""

    # Video generation
    default_video_model: str = "wan2.6-i2v-flash"
    dashscope_video_api_key: str = ""
    dashscope_video_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    dashscope_video_model: str = "wan2.6-i2v-flash"

    kling_video_api_key: str = ""
    kling_video_base_url: str = "https://api.klingai.com"
    kling_api_key: str = ""
    kling_base_url: str = "https://api.klingai.com"
    kling_video_model: str = "kling-v2-master"

    minimax_video_api_key: str = ""
    minimax_video_base_url: str = "https://api.minimaxi.chat"
    minimax_video_model: str = "video-01"

    doubao_video_api_key: str = ""
    doubao_video_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_api_key: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_video_model: str = ""

    # Security: whether to DNS-resolve user-supplied base URLs and reject private IPs
    # Set to false in dev environments where foreign domains may not resolve
    validate_base_url_dns: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def _normalize_debug(cls, value):
        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().lower()
        if normalized in {"release", "prod", "production", "off"}:
            return False
        if normalized in {"debug", "dev", "development", "on"}:
            return True
        return value

    @field_validator("default_llm_provider", "default_image_provider", "default_video_provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value):
        return str(value or "").strip().lower()

    class Config:
        env_file = ".env"


settings = Settings()
