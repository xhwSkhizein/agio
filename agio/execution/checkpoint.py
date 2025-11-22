"""
Checkpoint models for execution state management.

This module defines the data models for checkpoints, which capture the complete
state of an agent execution at a specific point in time.
"""

from datetime import datetime
from uuid import uuid4
from typing import Any
from pydantic import BaseModel, Field
from agio.domain.run import RunStatus
from agio.domain.metrics import AgentRunMetrics
from agio.domain.messages import Message


class ExecutionCheckpoint(BaseModel):
    """
    Execution Checkpoint - Complete state snapshot.
    
    Design principles:
    1. Self-contained - includes all information needed for restoration
    2. Immutable - cannot be modified after creation
    3. Serializable - supports JSON serialization
    """
    
    # Basic information
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str = Field(description="Parent Run ID")
    step_num: int = Field(description="Step number")
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Execution status
    status: RunStatus = Field(description="Run status at checkpoint")
    
    # Message context (core)
    messages: list[dict[str, Any]] = Field(
        description="Complete message history (conversation context)"
    )
    
    # Metrics snapshot
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Current metrics"
    )
    
    # Agent configuration snapshot
    agent_config: dict[str, Any] = Field(
        description="Agent configuration snapshot (for reproduction)"
    )
    
    # Optional: user modifications
    user_modifications: dict[str, Any] | None = Field(
        default=None,
        description="User modifications (for Fork)"
    )
    
    # Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    
    # Tags (for categorization and search)
    tags: list[str] = Field(
        default_factory=list,
        description="Tags"
    )
    
    # Description
    description: str | None = Field(
        default=None,
        description="Checkpoint description"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "ckpt_123",
                "run_id": "run_456",
                "step_num": 2,
                "status": "running",
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi!"}
                ],
                "description": "Before tool call"
            }
        }


class CheckpointMetadata(BaseModel):
    """Checkpoint metadata (for list display)."""
    
    id: str
    run_id: str
    step_num: int
    created_at: datetime
    status: RunStatus
    description: str | None
    tags: list[str]
    
    # Statistics
    message_count: int
    total_tokens: int
    
    # Whether has user modifications
    has_modifications: bool = False
