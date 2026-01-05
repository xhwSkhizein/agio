"""
Anthropic Model implementation - Pure LLM Interface
"""

import os
from typing import AsyncIterator

from pydantic import ConfigDict, Field, SecretStr

try:
    from anthropic import (
        APIConnectionError,
        APITimeoutError,
        AsyncAnthropic,
        RateLimitError,
    )
except ImportError:
    raise ImportError("Please install anthropic package: uv add anthropic")

from agio.llm.base import Model, StreamChunk
from agio.utils.logging import get_logger
from agio.utils.retry import retry_async

logger = get_logger(__name__)

# Retryable exceptions for Anthropic
ANTHROPIC_RETRYABLE = (
    APIConnectionError,
    RateLimitError,
    APITimeoutError,
)


class AnthropicModel(Model):
    """
    Anthropic Claude Model implementation.

    Supports Claude 3 series models (Opus, Sonnet, Haiku).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    model_name: str | None = Field(
        default=None,
        description="Actual model name for API calls (e.g., claude-3-5-sonnet-20241022)",
    )
    api_key: SecretStr | None = Field(default=None, exclude=True)
    base_url: str | None = Field(default=None, description="Custom API base URL")
    client: AsyncAnthropic | None = Field(default=None, exclude=True)

    max_tokens_to_sample: int = Field(default=4096, ge=1)

    def model_post_init(self, __context) -> None:
        """Initialize AsyncAnthropic client after model creation."""
        from agio.config import settings

        # Resolve API Key: argument > config > env
        resolved_api_key = None
        if self.api_key:
            resolved_api_key = self.api_key.get_secret_value()
        elif hasattr(settings, "anthropic_api_key") and settings.anthropic_api_key:
            resolved_api_key = settings.anthropic_api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("ANTHROPIC_API_KEY")

        if self.client is None:
            client_kwargs = {"api_key": resolved_api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self.client = AsyncAnthropic(**client_kwargs)

        # Call base class to enable tracking
        super().model_post_init(__context)

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Convert OpenAI format messages to Anthropic format."""
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                system_prompt = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                if "tool_calls" in msg:
                    content_blocks = []
                    if content:
                        content_blocks.append({"type": "text", "text": content})

                    for tool_call in msg["tool_calls"]:
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tool_call["id"],
                                "name": tool_call["function"]["name"],
                                "input": tool_call["function"]["arguments"],
                            }
                        )

                    anthropic_messages.append(
                        {"role": "assistant", "content": content_blocks}
                    )
                else:
                    anthropic_messages.append({"role": "assistant", "content": content})
            elif role == "tool":
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id"),
                                "content": content,
                            }
                        ],
                    }
                )

        return system_prompt, anthropic_messages

    def _convert_tools(self, tools: list[dict] | None) -> list[dict] | None:
        """Convert OpenAI format tools to Anthropic format."""
        if not tools:
            return None

        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    }
                )

        return anthropic_tools if anthropic_tools else None

    @retry_async(exceptions=ANTHROPIC_RETRYABLE)
    async def arun_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Call Anthropic API and return standardized streaming output.

        Args:
            messages: OpenAI format message list
            tools: OpenAI format tool definitions

        Yields:
            StreamChunk: Standardized streaming output chunk
        """
        system_prompt, anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        actual_model = self.model_name or self.name
        params = {
            "model": actual_model,
            "messages": anthropic_messages,
            "max_tokens": self.max_tokens or self.max_tokens_to_sample,
            "temperature": self.temperature,
            "stream": True,
        }

        if system_prompt:
            params["system"] = system_prompt

        if self.top_p is not None:
            params["top_p"] = self.top_p

        if anthropic_tools:
            params["tools"] = anthropic_tools

        logger.debug(
            "llm_request",
            model=actual_model,
            messages_count=len(anthropic_messages),
            tools_count=len(anthropic_tools) if anthropic_tools else 0,
            temperature=self.temperature,
            max_tokens=params["max_tokens"],
        )

        try:
            stream = await self.client.messages.create(**params)
        except Exception as e:
            logger.error(
                "llm_request_failed",
                model=actual_model,
                error=str(e),
                error_type=type(e).__name__,
                messages_count=len(anthropic_messages),
                tools_count=len(anthropic_tools) if anthropic_tools else 0,
                exc_info=True,
            )
            raise

        async for event in stream:
            stream_chunk = StreamChunk()

            if event.type == "content_block_delta":
                delta = event.delta

                if delta.type == "text_delta":
                    stream_chunk.content = delta.text

            elif event.type == "message_delta":
                if event.delta.stop_reason:
                    stream_chunk.finish_reason = event.delta.stop_reason

            elif event.type == "message_stop":
                stream_chunk.finish_reason = "stop"

            if (
                stream_chunk.content is not None
                or stream_chunk.tool_calls is not None
                or stream_chunk.finish_reason is not None
            ):
                yield stream_chunk


__all__ = ["AnthropicModel"]
