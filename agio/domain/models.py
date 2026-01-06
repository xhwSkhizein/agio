"""
Core domain models for Agio.

This module contains all core data models:
- Step: Unified step model that maps to LLM messages
- Run: Run lifecycle and status
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


def normalize_usage_metrics(usage_data: dict[str, Any] | None) -> dict[str, int | None]:
    """
    Normalize model usage metrics to unified format.

    Handles both OpenAI-style and unified-style metrics, including prompt caching.
    Ensures 'input_tokens' always represents the TOTAL input (including cache).

    Args:
        usage_data: Raw usage data from model

    Returns:
        dict with normalized keys: 
        - input_tokens (Total input)
        - output_tokens
        - total_tokens (input_tokens + output_tokens)
        - cache_read_tokens
        - cache_creation_tokens
    """
    if not usage_data:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cache_read_tokens": None,
            "cache_creation_tokens": None,
        }

    # Extract base tokens
    # OpenAI: prompt_tokens (Total)
    # Anthropic: input_tokens (Excludes cache)
    base_input = usage_data.get("input_tokens") or usage_data.get("prompt_tokens")
    output_tokens = usage_data.get("output_tokens") or usage_data.get(
        "completion_tokens"
    )

    # Extract cache details
    # OpenAI: cached_tokens
    # Anthropic: cache_read_tokens, cache_creation_tokens
    cache_read_tokens = (
        usage_data.get("cache_read_tokens")
        or usage_data.get("cache_read_input_tokens")
        or usage_data.get("cached_tokens")
    )
    cache_creation_tokens = usage_data.get("cache_creation_tokens") or usage_data.get(
        "cache_creation_input_tokens"
    )

    input_tokens = base_input
    # For Anthropic (where we have cache_read_tokens or cache_creation_tokens), 
    # the base_input usually excludes them.
    # For OpenAI, prompt_tokens (base_input) already includes them.
    # Detect provider style by key names or by checking if we need to sum up.
    # If we see cache_read_input_tokens or cache_creation_input_tokens, it's Anthropic style.
    if "cache_read_input_tokens" in usage_data or "cache_creation_input_tokens" in usage_data:
        # Anthropic style: sum them up to get Total Input
        if input_tokens is not None:
            input_tokens += (cache_read_tokens or 0) + (cache_creation_tokens or 0)
    elif "cache_read_tokens" in usage_data or "cache_creation_tokens" in usage_data:
        # Also Anthropic style if passed from my updated anthropic.py
        if input_tokens is not None:
            input_tokens += (cache_read_tokens or 0) + (cache_creation_tokens or 0)

    # Calculate total_tokens (Input + Output)
    total_tokens = usage_data.get("total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
    }


class StepMetrics(BaseModel):
    """
    Metrics for a single Step.

    Different fields are relevant for different step types:
    - Assistant steps: token counts, model info, latency
    - Tool steps: execution time
    """

    # Timing
    duration_ms: float | None = None
    exec_start_at: datetime | None = (
        None  # Actual execution start time (for LLM calls or tool execution)
    )
    exec_end_at: datetime | None = None  # Actual execution end time

    # Token usage (for assistant/model steps)
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None

    # Model info
    model_name: str | None = None
    provider: str | None = None

    # Latency
    first_token_latency_ms: float | None = None

    # Tool execution (for tool steps)
    tool_exec_time_ms: float | None = None
    tool_exec_start_at: float | None = None
    tool_exec_end_at: float | None = None


class RunMetrics(BaseModel):
    """
    Metrics for a single Run (Agent).

    Supports merge for aggregating metrics from child runs.
    """

    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0

    # Token usage
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    # Execution stats
    steps_count: int = 0
    tool_calls_count: int = 0
    tool_errors_count: int = 0

    # Latency
    first_token_latency: float | None = None
    response_latency: float | None = None

    def merge(
        self,
        other: "RunMetrics",
        mode: str = "sequential",
    ) -> None:
        """
        Merge another RunMetrics into this one.

        Args:
            other: RunMetrics to merge
            mode: "sequential" or "parallel"
                - sequential: duration sums, first_token_latency uses first
                - parallel: duration takes max, first_token_latency takes min
        """
        if mode == "parallel":
            # Parallel: duration is max (wall clock), latency is min (first response)
            self.duration = max(self.duration, other.duration)
            if other.first_token_latency is not None:
                if self.first_token_latency is None:
                    self.first_token_latency = other.first_token_latency
                else:
                    self.first_token_latency = min(
                        self.first_token_latency, other.first_token_latency
                    )
        else:
            # Sequential: duration sums, keep first latency
            self.duration += other.duration
            if self.first_token_latency is None:
                self.first_token_latency = other.first_token_latency

        # Token usage always sums
        self.total_tokens += other.total_tokens
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_creation_tokens += other.cache_creation_tokens

        # Execution stats sum
        self.steps_count += other.steps_count
        self.tool_calls_count += other.tool_calls_count
        self.tool_errors_count += other.tool_errors_count
        self.nodes_executed += other.nodes_executed
        self.branches_executed += other.branches_executed
        self.iterations += other.iterations


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

    # --- Runnable Binding (for unified Fork/Resume) ---
    runnable_id: str | None = None  # Agent ID that created this step
    runnable_type: str | None = None  # "agent"

    # --- Core Content (Standard LLM Message) ---
    role: MessageRole
    content: str | None = None  # LLM message content
    content_for_user: str | None = (
        None  # Display content for frontend (preferred for UI)
    )
    reasoning_content: str | None = (
        None  # Reasoning content (e.g., DeepSeek thinking mode)
    )

    # Assistant-specific fields
    tool_calls: list[dict] | None = None

    # Tool-specific fields
    tool_call_id: str | None = None
    name: str | None = None

    # --- Metadata ---
    metrics: StepMetrics | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    # --- Multi-Agent Context ---
    parent_run_id: str | None = None  # Parent run ID for nested executions

    # --- Observability (new) ---
    trace_id: str | None = None  # Trace ID for distributed tracing
    span_id: str | None = None  # Span ID
    parent_span_id: str | None = None  # Parent span ID
    depth: int = 0  # Nesting depth

    # --- LLM Call Context (for assistant steps) ---
    llm_messages: list[dict[str, Any]] | None = (
        None  # Complete message list sent to LLM
    )
    llm_tools: list[dict[str, Any]] | None = None  # Tool definitions sent to LLM
    llm_request_params: dict[str, Any] | None = (
        None  # Request parameters (temperature, max_tokens, etc.)
    )

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


class Run(BaseModel):
    """
    Unified Run metadata for Agent.

    Run 是轻量级的元数据记录，主要用于：
    1. 快速查询历史记录
    2. 聚合展示运行状态和指标
    3. 引用关联的 Steps（通过 session_id）

    核心数据存储在 Steps 中。
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    runnable_id: str  # Agent ID
    runnable_type: str = "agent"  # "agent"
    session_id: str  # Associated Steps' session_id
    user_id: str | None = None

    input_query: str
    status: RunStatus = RunStatus.STARTING

    # Aggregated metadata
    response_content: str | None = None  # Final response content (extracted from Steps)
    metrics: RunMetrics = Field(default_factory=RunMetrics)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # --- Multi-Agent Context ---
    parent_run_id: str | None = None  # Parent run ID for nested executions

    # --- Observability ---
    trace_id: str | None = None  # Associated trace ID


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
