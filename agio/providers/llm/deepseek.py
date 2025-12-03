"""
DeepSeek Model implementation - Inherits from OpenAIModel

DeepSeek API is compatible with OpenAI format.
"""

import os

from pydantic import ConfigDict, Field

from agio.providers.llm.openai import OpenAIModel


class DeepseekModel(OpenAIModel):
    """
    DeepSeek Model implementation.

    DeepSeek uses OpenAI-compatible API format, so inherits OpenAIModel.
    Only overrides API Key and Base URL resolution logic.
    """

    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(default="deepseek/deepseek-chat")
    name: str = Field(default="deepseek-chat")
    base_url: str | None = Field(default=None)

    def model_post_init(self, __context) -> None:
        """Override to use DeepSeek-specific API key and base URL."""
        from agio.config import settings
        
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

        # Call grandparent's model_post_init (skip OpenAIModel to avoid double client init)
        from agio.providers.llm.base import Model

        Model.model_post_init(self, __context)


__all__ = ["DeepseekModel"]
