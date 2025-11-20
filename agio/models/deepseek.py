"""
DeepSeek Model 实现 - 继承自 OpenAIModel

DeepSeek API 兼容 OpenAI 格式，因此直接继承 OpenAIModel。
"""

import os
from pydantic import Field, ConfigDict
from agio.models.openai import OpenAIModel
from agio.config import settings


class Deepseek(OpenAIModel):
    """
    DeepSeek Model 实现。

    DeepSeek 使用与 OpenAI 兼容的 API 格式，因此继承 OpenAIModel。
    只需要覆盖 API Key 和 Base URL 的解析逻辑。

    Examples:
        >>> model = Deepseek(
        ...     id="deepseek/deepseek-chat",
        ...     name="deepseek-chat",
        ...     api_key="sk-xxx"
        ... )
        >>> async for chunk in model.arun_stream(messages):
        ...     if chunk.content:
        ...         print(chunk.content, end="")
    """

    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(default="deepseek/deepseek-chat")
    name: str = Field(default="deepseek-chat")
    base_url: str | None = Field(default=None)

    def model_post_init(self, __context) -> None:
        """Override to use DeepSeek-specific API key and base URL."""
        # Resolve API Key: deepseek_api_key > DEEPSEEK_API_KEY
        resolved_api_key = None
        if self.api_key:
            resolved_api_key = self.api_key.get_secret_value()
        elif settings.deepseek_api_key:
            resolved_api_key = settings.deepseek_api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("DEEPSEEK_API_KEY")

        # Resolve Base URL
        resolved_base_url = (
            self.base_url
            or settings.deepseek_base_url
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        )

        # Create client
        if self.client is None:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )
