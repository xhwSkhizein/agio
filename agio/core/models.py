"""
Core domain models for Agio.

This module contains all core data models:
- Step: Unified step model that maps to LLM messages
- AgentRun: Run lifecycle and status
- Metrics: Performance and usage metrics
- Session: Conversation session
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Enums
# ============================================================================


class MessageRole(str, Enum):
    """Standard LLM message roles"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class RunStatus(str, Enum):
    """Agent run status"""

    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Metrics Models
# ============================================================================


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


class AgentRunMetrics(BaseModel):
    """Metrics for a single Agent Run (User Query -> Final Response)"""

    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0

    # Token usage
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Execution stats
    steps_count: int = 0
    tool_calls_count: int = 0
    tool_errors_count: int = 0

    # Latency
    first_token_timestamp: float | None = None
    response_latency: float | None = None


# ============================================================================
# Core Models
# ============================================================================


class Step(BaseModel):
    """
    Unified Step model that directly maps to LLM Message structure.

    This is the core data model that:
    1. Stores conversation history in the database
    2. Streams to the frontend in real-time
    3. Builds LLM context with zero conversion

    The structure exactly matches OpenAI's message format, with additional
    metadata fields for tracking and metrics.
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


class GenerationReference(BaseModel):
    """Reference to the LLM call that generated content"""

    model_config = ConfigDict(protected_namespaces=())

    run_id: str  # Run ID
    step_id: str  # Step ID that performed the generation
    model_id: str

    # Key parameters snapshot for quick reference
    context_window_size: int | None = None
    citations: list[str] = Field(default_factory=list)


class AgentRunSummary(BaseModel):
    """Summary of an agent run"""

    content: str
    created_at: datetime = Field(default_factory=datetime.now)
    reference: GenerationReference | None = None


class AgentRun(BaseModel):
    """
    Agent run metadata and aggregation.
    
    Run 是轻量级的元数据记录，主要用于：
    1. 快速查询历史记录
    2. 聚合展示运行状态和指标
    3. 引用关联的 Steps（通过 session_id）
    
    核心数据存储在 Steps 中。
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    session_id: str  # 关联 Steps 的 session_id
    user_id: str | None = None

    input_query: str
    status: RunStatus = RunStatus.STARTING

    # 聚合的元数据
    response_content: str | None = None  # 最终响应内容（从 Steps 提取）
    metrics: AgentRunMetrics = Field(default_factory=AgentRunMetrics)
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AgentSession(BaseModel):
    """Conversation session state"""

    session_id: str
    user_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class MemoryCategory(str, Enum):
    """Categories for agent memories"""

    USER_PREFERENCE = "user_preference"  # User preferences
    FACT = "fact"  # Factual information
    SUMMARY = "summary"  # Conversation summaries
    OBSERVATION = "observation"  # Observations
    CONCEPT = "concept"  # Abstract concepts
    OTHER = "other"


class AgentMemoriedContent(BaseModel):
    """Content stored in agent memory"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    category: MemoryCategory = MemoryCategory.OTHER
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.5  # Importance score (0-1)

    created_at: datetime = Field(default_factory=datetime.now)
    source_run_id: str | None = None  # Original conversation Run ID

    # Reference to the LLM call that extracted this memory
    reference: GenerationReference | None = None
