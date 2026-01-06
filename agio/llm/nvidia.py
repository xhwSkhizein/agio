"""
NVIDIA Model implementation - Inherits from OpenAIModel

NVIDIA API is compatible with OpenAI format and includes reasoning_content.
"""

import os
from typing import AsyncIterator

from pydantic import ConfigDict, Field

from agio.llm.base import StreamChunk
from agio.llm.openai import OpenAIModel


class NvidiaModel(OpenAIModel):
    """
    NVIDIA Model implementation.

    NVIDIA uses OpenAI-compatible API format, so inherits OpenAIModel.
    Handles NVIDIA-specific logic including reasoning_content.
    """

    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(default="nvidia/nvidia-chat")
    name: str = Field(default="nvidia-chat")
    base_url: str | None = Field(default=None)

    def model_post_init(self, __context) -> None:
        """Override to use NVIDIA-specific API key and base URL."""
        from agio.config import settings

        # Resolve API Key: nvidia_api_key > NVIDIA_API_KEY
        resolved_api_key = None
        if self.api_key:
            resolved_api_key = self.api_key.get_secret_value()
        elif settings.nvidia_api_key:
            resolved_api_key = settings.nvidia_api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("NVIDIA_API_KEY")

        # Resolve Base URL
        resolved_base_url = (
            self.base_url
            or settings.nvidia_base_url
            or os.getenv("NVIDIA_BASE_URL")
            or "https://integrate.api.nvidia.com/v1"
        )

        # Create client
        if self.client is None:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )

        # Call grandparent's model_post_init (skip OpenAIModel to avoid double client init)
        from agio.llm.base import Model

        Model.model_post_init(self, __context)

    async def arun_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Call NVIDIA API.
        
        NVIDIA response chunks include reasoning_content which is already handled by OpenAIModel.arun_stream.
        """
        async for chunk in super().arun_stream(messages, tools=tools):
            yield chunk


__all__ = ["NvidiaModel"]
