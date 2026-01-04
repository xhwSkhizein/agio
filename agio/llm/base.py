"""
Model abstraction layer - Pure LLM Interface

Responsibilities:
- Encapsulate different LLM provider APIs
- Provide unified streaming interface
- Standardize output format

Does NOT handle:
- Tool Loop logic
- Event wrapping
- State management
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from pydantic import BaseModel, ConfigDict, Field


class StreamChunk(BaseModel):
    """
    Minimal unit of LLM streaming output.

    All Model implementations must standardize their vendor-specific
    streaming output to this format.
    """

    model_config = ConfigDict(frozen=False)

    content: str | None = Field(default=None, description="Text content delta")
    reasoning_content: str | None = Field(
        default=None, description="Reasoning content delta (e.g., DeepSeek thinking mode)"
    )
    tool_calls: list[dict] | None = Field(
        default=None, description="Tool calls delta (OpenAI format)"
    )
    usage: dict[str, int] | None = Field(
        default=None,
        description="Token usage stats {input_tokens, output_tokens, total_tokens}",
    )
    finish_reason: str | None = Field(
        default=None, description="Finish reason: stop, tool_calls, length, etc."
    )


class Model(BaseModel, ABC):
    """
    Unified Model abstract base class.

    All LLM implementations (OpenAI, DeepSeek, Anthropic, etc.) should inherit
    this class and implement the arun_stream() method.
    """

    id: str = Field(description="Model identifier, format: provider/model-name")
    name: str = Field(description="Model name")

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def model_post_init(self, __context) -> None:
        """Post-initialization hook for model configuration."""
        pass

    @abstractmethod
    async def arun_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Unified streaming interface.

        Args:
            messages: Message list, standard OpenAI format
            tools: Tool definition list, OpenAI format

        Yields:
            StreamChunk: Streaming output chunk
        """
        pass


__all__ = ["Model", "StreamChunk"]
