"""
Anthropic Model 实现 - Pure LLM Interface
"""

import os
from typing import AsyncIterator

from pydantic import ConfigDict, Field, SecretStr

try:
    from anthropic import APIConnectionError, APITimeoutError, AsyncAnthropic, RateLimitError
except ImportError:
    raise ImportError("Please install anthropic package: uv add anthropic")

from agio.core.config import settings
from agio.components.models.base import Model, StreamChunk
from agio.utils.retry import retry_async

# Retryable exceptions for Anthropic
ANTHROPIC_RETRYABLE = (
    APIConnectionError,
    RateLimitError,
    APITimeoutError,
)


class AnthropicModel(Model):
    """
    Anthropic Claude Model 实现。

    支持 Claude 3 系列模型 (Opus, Sonnet, Haiku)。

    Examples:
        >>> model = AnthropicModel(
        ...     id="anthropic/claude-3-opus-20240229",
        ...     name="claude-3-opus-20240229",
        ...     api_key="sk-ant-xxx"
        ... )
        >>> messages = [
        ...     {"role": "user", "content": "Hello!"}
        ... ]
        >>> async for chunk in model.arun_stream(messages):
        ...     if chunk.content:
        ...         print(chunk.content, end="")
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    # Anthropic specific fields
    model_name: str | None = Field(default=None, description="Actual model name for API calls (e.g., claude-3-5-sonnet-20241022)")
    api_key: SecretStr | None = Field(default=None, exclude=True)
    client: AsyncAnthropic | None = Field(default=None, exclude=True)

    # Claude specific parameters
    max_tokens_to_sample: int = Field(default=4096, ge=1)

    def model_post_init(self, __context) -> None:
        """Initialize AsyncAnthropic client after model creation."""
        # Resolve API Key: argument > config > env
        resolved_api_key = None
        if self.api_key:
            resolved_api_key = self.api_key.get_secret_value()
        elif hasattr(settings, "anthropic_api_key") and settings.anthropic_api_key:
            resolved_api_key = settings.anthropic_api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("ANTHROPIC_API_KEY")

        # Create client if not provided
        if self.client is None:
            self.client = AsyncAnthropic(api_key=resolved_api_key)

        super().model_post_init(__context)

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """
        Convert OpenAI format messages to Anthropic format.

        Args:
            messages: OpenAI format messages

        Returns:
            (system_prompt, anthropic_messages)
        """
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                # Anthropic uses separate system parameter
                system_prompt = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                # Handle tool calls if present
                if "tool_calls" in msg:
                    # Anthropic format for tool use
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

                    anthropic_messages.append({"role": "assistant", "content": content_blocks})
                else:
                    anthropic_messages.append({"role": "assistant", "content": content})
            elif role == "tool":
                # Anthropic format for tool results
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
        调用 Anthropic API 并返回标准化的流式输出。

        Args:
            messages: OpenAI 格式的消息列表
            tools: OpenAI 格式的工具定义

        Yields:
            StreamChunk: 标准化的流式输出块
        """
        # Convert messages
        system_prompt, anthropic_messages = self._convert_messages(messages)

        # Convert tools
        anthropic_tools = self._convert_tools(tools)

        # Build request parameters
        # Use model_name for API calls, fallback to name if not set
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

        # Call Anthropic API
        stream = await self.client.messages.create(**params)

        # Convert Anthropic stream to StreamChunk
        async for event in stream:
            stream_chunk = StreamChunk()

            # Handle different event types
            if event.type == "content_block_delta":
                delta = event.delta

                if delta.type == "text_delta":
                    stream_chunk.content = delta.text

                elif delta.type == "input_json_delta":
                    # Tool call in progress
                    # Anthropic sends partial JSON, we'll accumulate it
                    # For now, we'll skip partial tool calls
                    pass

            elif event.type == "content_block_start":
                # Start of a content block (text or tool use)
                if event.content_block.type == "tool_use":
                    # Tool call starting
                    # We'll handle complete tool calls in content_block_stop
                    pass

            elif event.type == "message_delta":
                # Message-level delta (e.g., stop_reason)
                if event.delta.stop_reason:
                    stream_chunk.finish_reason = event.delta.stop_reason

            elif event.type == "message_stop":
                # End of message
                stream_chunk.finish_reason = "stop"

            # Only yield if there's actual data
            if (
                stream_chunk.content is not None
                or stream_chunk.tool_calls is not None
                or stream_chunk.finish_reason is not None
            ):
                yield stream_chunk
