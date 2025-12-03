"""
LLM Call Log data models.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class LLMCallLog(BaseModel):
    """Complete LLM call log with full request/response details."""

    # Identifiers
    id: str = Field(description="Unique log ID (UUID)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Call start timestamp",
    )

    # Context identifiers for filtering
    agent_name: str | None = Field(default=None, description="Agent name if available")
    session_id: str | None = Field(default=None, description="Session ID if available")
    run_id: str | None = Field(default=None, description="Run ID if available")

    # Model info
    model_id: str = Field(description="Model identifier (e.g., openai/gpt-4o)")
    model_name: str | None = Field(
        default=None, description="Actual model name for API call"
    )
    provider: str = Field(description="Provider name (openai/anthropic/deepseek)")

    # Full request parameters
    request: dict[str, Any] = Field(
        default_factory=dict,
        description="Complete request parameters sent to LLM API",
    )
    messages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Full messages array sent to LLM",
    )
    tools: list[dict[str, Any]] | None = Field(
        default=None,
        description="Tool definitions if provided",
    )

    # Full response
    response_content: str | None = Field(
        default=None, description="Complete text response from LLM"
    )
    response_tool_calls: list[dict[str, Any]] | None = Field(
        default=None, description="Tool calls from response"
    )
    finish_reason: str | None = Field(default=None, description="LLM finish reason")

    # Status
    status: Literal["running", "completed", "error"] = Field(
        default="running", description="Call status"
    )
    error: str | None = Field(default=None, description="Error message if failed")

    # Metrics
    duration_ms: float | None = Field(default=None, description="Total call duration")
    first_token_ms: float | None = Field(
        default=None, description="Time to first token"
    )
    input_tokens: int | None = Field(default=None, description="Input token count")
    output_tokens: int | None = Field(default=None, description="Output token count")
    total_tokens: int | None = Field(default=None, description="Total token count")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class LLMLogQuery(BaseModel):
    """Query parameters for filtering LLM logs."""

    agent_name: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    model_id: str | None = None
    provider: str | None = None
    status: Literal["running", "completed", "error"] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


__all__ = ["LLMCallLog", "LLMLogQuery"]
