"""
Unified Step model that directly maps to LLM Message structure.

This replaces both AgentRunStep and StoredEvent, providing a single
source of truth for conversation history that aligns with native LLM formats.
"""

from enum import Enum
from datetime import datetime
from uuid import uuid4
from typing import Any
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Standard LLM message roles"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class StepMetrics(BaseModel):
    """
    Metrics for a single Step.
    
    Different fields are relevant for different step types:
    - Assistant steps: token counts, model info, latency
    - Tool steps: execution time
    """
    # Timing
    duration_ms: float | None = None
    
    # Token usage (for assistant/model steps)
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_tokens: int | None = None
    
    # Model info
    model_name: str | None = None
    provider: str | None = None
    
    # Latency
    first_token_latency_ms: float | None = None
    
    # Tool execution (for tool steps)
    tool_exec_time_ms: float | None = None
    tool_exec_start_at: float | None = None
    tool_exec_end_at: float | None = None


class Step(BaseModel):
    """
    Unified Step model that directly maps to LLM Message structure.
    
    This is the core data model that:
    1. Stores conversation history in the database
    2. Streams to the frontend in real-time
    3. Builds LLM context with zero conversion
    
    The structure exactly matches OpenAI's message format, with additional
    metadata fields for tracking and metrics.
    
    Examples:
        User step:
            Step(
                role=MessageRole.USER,
                content="Hello",
                session_id="session_123",
                run_id="run_456",
                sequence=1
            )
        
        Assistant step with tool calls:
            Step(
                role=MessageRole.ASSISTANT,
                content="Let me search for that",
                tool_calls=[{
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "search", "arguments": "{}"}
                }],
                session_id="session_123",
                run_id="run_456",
                sequence=2
            )
        
        Tool result step:
            Step(
                role=MessageRole.TOOL,
                content="Search results: ...",
                tool_call_id="call_123",
                name="search",
                session_id="session_123",
                run_id="run_456",
                sequence=3
            )
    """
    
    # --- Indexing & Association ---
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    run_id: str  # Logical grouping for a single user query → response cycle
    sequence: int  # Global sequence within session (1, 2, 3, ...)
    
    # --- Core Content (Standard LLM Message) ---
    role: MessageRole
    content: str | None = None
    
    # Assistant-specific fields
    tool_calls: list[dict] | None = None
    
    # Tool-specific fields
    tool_call_id: str | None = None
    name: str | None = None
    
    # --- Metadata ---
    metrics: StepMetrics | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    
    def to_message_dict(self) -> dict[str, Any]:
        """
        Convert to LLM message format (exclude metadata).
        
        This is used for building context to send to the LLM.
        Only includes fields that are part of the standard message format.
        
        Returns:
            dict: Message in OpenAI format
        """
        msg: dict[str, Any] = {"role": self.role.value}
        
        if self.content is not None:
            msg["content"] = self.content
        
        if self.tool_calls is not None:
            msg["tool_calls"] = self.tool_calls
        
        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id
        
        if self.name is not None:
            msg["name"] = self.name
        
        return msg
    
    def is_user_step(self) -> bool:
        """Check if this is a user message"""
        return self.role == MessageRole.USER
    
    def is_assistant_step(self) -> bool:
        """Check if this is an assistant message"""
        return self.role == MessageRole.ASSISTANT
    
    def is_tool_step(self) -> bool:
        """Check if this is a tool result message"""
        return self.role == MessageRole.TOOL
    
    def has_tool_calls(self) -> bool:
        """Check if this assistant step has tool calls"""
        return self.is_assistant_step() and bool(self.tool_calls)
