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


class RunMetrics(BaseModel):
    """
    Metrics for a single Run (Agent or Workflow).
    
    Supports merge for aggregating metrics from child runs.
    """

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

    # Workflow-specific
    nodes_executed: int = 0
    branches_executed: int = 0  # ParallelWorkflow
    iterations: int = 0  # LoopWorkflow

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
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens

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
    runnable_id: str | None = None  # Agent ID or Workflow ID that created this step
    runnable_type: str | None = None  # "agent" or "workflow"

    # --- Core Content (Standard LLM Message) ---
    role: MessageRole
    content: str | None = None
    reasoning_content: str | None = None  # Reasoning content (e.g., DeepSeek thinking mode)

    # Assistant-specific fields
    tool_calls: list[dict] | None = None

    # Tool-specific fields
    tool_call_id: str | None = None
    name: str | None = None

    # --- Metadata ---
    metrics: StepMetrics | None = None
    created_at: datetime = Field(default_factory=datetime.now)

    # --- Multi-Agent Context (new) ---
    workflow_id: str | None = None  # Parent workflow ID

    # --- Workflow Node Tracking (new) ---
    node_id: str | None = None  # Corresponding WorkflowNode.id
    parent_run_id: str | None = None  # Parent run ID for nested executions
    branch_key: str | None = None  # Branch identifier for parallel execution
    iteration: int | None = None  # Loop iteration number (1-based)

    # --- Observability (new) ---
    trace_id: str | None = None  # Trace ID for distributed tracing
    span_id: str | None = None  # Span ID
    parent_span_id: str | None = None  # Parent span ID
    depth: int = 0  # Nesting depth in workflow

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
    Unified Run metadata for Agent and Workflow.
    
    Run 是轻量级的元数据记录，主要用于：
    1. 快速查询历史记录
    2. 聚合展示运行状态和指标
    3. 引用关联的 Steps（通过 session_id）
    
    核心数据存储在 Steps 中。
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    runnable_id: str  # Agent or Workflow ID
    runnable_type: str = "agent"  # "agent" or "workflow"
    session_id: str  # 关联 Steps 的 session_id
    user_id: str | None = None

    input_query: str
    status: RunStatus = RunStatus.STARTING

    # 聚合的元数据
    response_content: str | None = None  # 最终响应内容（从 Steps 提取）
    metrics: RunMetrics = Field(default_factory=RunMetrics)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # --- Multi-Agent Context ---
    workflow_id: str | None = None  # Parent workflow ID
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
