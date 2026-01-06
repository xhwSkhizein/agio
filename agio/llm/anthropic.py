"""
Anthropic Model implementation - Pure LLM Interface
"""

import json
import os
from typing import Any, AsyncIterator

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

        logger.info(
            "AnthropicModel initialized",
            model_name=self.model_name,
            use_key=resolved_api_key[:10] if resolved_api_key else "None",
        )

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
                reasoning = msg.get("reasoning_content")
                if "tool_calls" in msg or reasoning:
                    content_blocks = []

                    if reasoning:
                        content_blocks.append(
                            {"type": "thinking", "thinking": reasoning}
                        )

                    if content:
                        content_blocks.append({"type": "text", "text": content})

                    if "tool_calls" in msg:
                        for tool_call in msg["tool_calls"]:
                            func = tool_call["function"]
                            args = func["arguments"]
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    logger.error(
                                        "failed_to_decode_tool_arguments",
                                        arguments=args,
                                    )

                            content_blocks.append(
                                {
                                    "type": "tool_use",
                                    "id": tool_call["id"],
                                    "name": func["name"],
                                    "input": args,
                                }
                            )

                    anthropic_messages.append(
                        {"role": "assistant", "content": content_blocks}
                    )
                else:
                    anthropic_messages.append({"role": "assistant", "content": content})
            elif role == "tool":
                # Ensure tool result content is a string
                tool_result_content = content
                if not isinstance(tool_result_content, str):
                    tool_result_content = json.dumps(tool_result_content)

                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id"),
                                "content": tool_result_content,
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

        logger.info(
            "llm_request",
            model=actual_model,
            messages_count=len(anthropic_messages),
            tools_count=len(anthropic_tools) if anthropic_tools else 0,
            temperature=self.temperature,
            max_tokens=params["max_tokens"],
            detail=json.dumps(params, indent=2, ensure_ascii=False),
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

        # Track tool calls being built during streaming
        tool_calls_buffer = {}
        # Track usage
        usage_info = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }

        async for event in stream:
            stream_chunk = StreamChunk()

            if event.type == "message_start":
                if hasattr(event.message, "usage"):
                    usage = event.message.usage
                    usage_info["input_tokens"] = getattr(usage, "input_tokens", 0)
                    usage_info["output_tokens"] = getattr(usage, "output_tokens", 0)
                    usage_info["cache_read_tokens"] = getattr(
                        usage, "cache_read_input_tokens", 0
                    )
                    usage_info["cache_creation_tokens"] = getattr(
                        usage, "cache_creation_input_tokens", 0
                    )

                    # Normalize usage for consistency
                    from agio.domain.models import normalize_usage_metrics

                    stream_chunk.usage = normalize_usage_metrics(
                        {
                            "input_tokens": usage_info["input_tokens"],
                            "output_tokens": usage_info["output_tokens"],
                            "cache_read_tokens": usage_info["cache_read_tokens"],
                            "cache_creation_tokens": usage_info["cache_creation_tokens"],
                        }
                    )

            elif event.type == "content_block_start":
                if event.content_block.type == "tool_use":
                    index = event.index
                    tool_calls_buffer[index] = {
                        "id": event.content_block.id,
                        "name": event.content_block.name,
                        "input": "",
                    }

            elif event.type == "content_block_delta":
                delta = event.delta

                if delta.type == "text_delta":
                    stream_chunk.content = delta.text
                elif delta.type == "thinking_delta":
                    stream_chunk.reasoning_content = delta.thinking
                elif delta.type == "input_json_delta":
                    index = event.index
                    if index in tool_calls_buffer:
                        tool_calls_buffer[index]["input"] += delta.partial_json

            elif event.type == "content_block_stop":
                index = event.index
                if index in tool_calls_buffer:
                    tool_call = tool_calls_buffer[index]
                    stream_chunk.tool_calls = [
                        {
                            "index": index,
                            "id": tool_call["id"],
                            "type": "function",
                            "function": {
                                "name": tool_call["name"],
                                "arguments": tool_call["input"],
                            },
                        }
                    ]
                    # Note: We emit the tool call when it's complete
                    # or should we emit deltas? Agio seems to prefer chunks.
                    # Given the current structure, we'll emit the full tool call at block stop.

            elif event.type == "message_delta":
                if hasattr(event, "usage"):
                    usage = event.usage
                    if hasattr(usage, "output_tokens"):
                        usage_info["output_tokens"] = usage.output_tokens
                    if hasattr(usage, "input_tokens"):
                        usage_info["input_tokens"] = usage.input_tokens
                    if hasattr(usage, "cache_read_input_tokens"):
                        usage_info["cache_read_tokens"] = usage.cache_read_input_tokens
                    if hasattr(usage, "cache_creation_input_tokens"):
                        usage_info["cache_creation_tokens"] = (
                            usage.cache_creation_input_tokens
                        )

                    # Normalize usage for consistency
                    from agio.domain.models import normalize_usage_metrics

                    stream_chunk.usage = normalize_usage_metrics(
                        {
                            "input_tokens": usage_info["input_tokens"],
                            "output_tokens": usage_info["output_tokens"],
                            "cache_read_tokens": usage_info["cache_read_tokens"],
                            "cache_creation_tokens": usage_info["cache_creation_tokens"],
                        }
                    )

                if event.delta.stop_reason:
                    # Anthropic stop reasons: end_turn, max_tokens, stop_sequence, tool_use
                    stop_reason = event.delta.stop_reason
                    if stop_reason == "tool_use":
                        stream_chunk.finish_reason = "tool_calls"
                    else:
                        stream_chunk.finish_reason = stop_reason

            elif event.type == "message_stop":
                if stream_chunk.finish_reason is None:
                    stream_chunk.finish_reason = "stop"

            if (
                stream_chunk.content is not None
                or stream_chunk.reasoning_content is not None
                or stream_chunk.tool_calls is not None
                or stream_chunk.usage is not None
                or stream_chunk.finish_reason is not None
            ):
                yield stream_chunk


__all__ = ["AnthropicModel"]
