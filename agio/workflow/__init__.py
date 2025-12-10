"""
Workflow module for multi-agent orchestration.

This module provides:
- Runnable protocol for unified Agent/Workflow interface
- Workflow types: Pipeline, Loop, Parallel
- InputMapping for input construction
- ConditionEvaluator for conditional execution
"""

from agio.workflow.protocol import Runnable, RunContext, RunOutput, RunMetrics
from agio.workflow.mapping import InputMapping
from agio.workflow.store import OutputStore
from agio.workflow.condition import ConditionEvaluator
from agio.workflow.stage import Stage
from agio.workflow.base import BaseWorkflow
from agio.workflow.pipeline import PipelineWorkflow
from agio.workflow.loop import LoopWorkflow
from agio.workflow.parallel import ParallelWorkflow
from agio.workflow.engine import WorkflowEngine
from agio.workflow.runnable_tool import (
    RunnableTool,
    as_tool,
    CircularReferenceError,
    MaxDepthExceededError,
    DEFAULT_MAX_DEPTH,
)

__all__ = [
    # Protocol
    "Runnable",
    "RunContext",
    "RunOutput",
    "RunMetrics",
    # Core
    "InputMapping",
    "OutputStore",
    "ConditionEvaluator",
    "Stage",
    # Workflow types
    "BaseWorkflow",
    "PipelineWorkflow",
    "LoopWorkflow",
    "ParallelWorkflow",
    # Engine
    "WorkflowEngine",
    # Runnable as Tool
    "RunnableTool",
    "as_tool",
    "CircularReferenceError",
    "MaxDepthExceededError",
    "DEFAULT_MAX_DEPTH",
]
