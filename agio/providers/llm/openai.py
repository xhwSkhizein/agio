"""
OpenAI Model implementation - Pure LLM Interface
"""

import os
from typing import AsyncIterator

from pydantic import ConfigDict, Field, SecretStr

try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AsyncOpenAI,
        InternalServerError,
        RateLimitError,
    )
except ImportError:
    raise ImportError("Please install openai package: pip install openai")

from agio.providers.llm.base import Model, StreamChunk
from agio.utils.retry import retry_async

# Retryable exceptions for OpenAI
OPENAI_RETRYABLE = (
    APIConnectionError,
    RateLimitError,
    InternalServerError,
    APITimeoutError,
)


class OpenAIModel(Model):
    """
    OpenAI Model implementation.

    Supports GPT-4, GPT-3.5-turbo and all OpenAI API compatible models.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    model_name: str | None = Field(
        default=None,
        description="Actual model name for API calls (e.g., gpt-4o-mini)",
    )
    api_key: SecretStr | None = Field(default=None, exclude=True)
    base_url: str | None = Field(default=None)
    client: AsyncOpenAI | None = Field(default=None, exclude=True)

    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)

    def model_post_init(self, __context) -> None:
        """Initialize AsyncOpenAI client after model creation."""
        from agio.config import settings

        # Resolve API Key: argument > config > env
        resolved_api_key = None
        if self.api_key:
            resolved_api_key = self.api_key.get_secret_value()
        elif settings.openai_api_key:
            resolved_api_key = settings.openai_api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("OPENAI_API_KEY")

        # Resolve Base URL
        resolved_base_url = (
            self.base_url or settings.openai_base_url or os.getenv("OPENAI_BASE_URL")
        )

        # Create client if not provided
        if self.client is None:
            self.client = AsyncOpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )

        super().model_post_init(__context)

    @retry_async(exceptions=OPENAI_RETRYABLE)
    async def arun_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Call OpenAI API and return standardized streaming output.

        Args:
            messages: OpenAI format message list
            tools: OpenAI format tool definitions

        Yields:
            StreamChunk: Standardized streaming output chunk
        """
        actual_model = self.model_name or self.name
        params = {
            "model": actual_model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens

        if tools:
            params["tools"] = tools

        stream = await self.client.chat.completions.create(**params)

        async for chunk in stream:
            stream_chunk = StreamChunk()

            if chunk.usage:
                stream_chunk.usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }

            if chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    stream_chunk.content = delta.content

                # Handle reasoning_content (DeepSeek thinking mode)
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    stream_chunk.reasoning_content = delta.reasoning_content

                if delta.tool_calls:
                    stream_chunk.tool_calls = [tc.model_dump() for tc in delta.tool_calls]

                if choice.finish_reason:
                    stream_chunk.finish_reason = choice.finish_reason

            if (
                stream_chunk.content is not None
                or stream_chunk.reasoning_content is not None
                or stream_chunk.tool_calls is not None
                or stream_chunk.usage is not None
            ):
                yield stream_chunk


__all__ = ["OpenAIModel"]
