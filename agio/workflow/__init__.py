"""
Workflow module for multi-agent orchestration.

This module provides:
- Runnable protocol for unified Agent/Workflow interface
- Workflow types: Pipeline, Loop, Parallel
- InputMapping for input construction
- ConditionEvaluator for conditional execution
- WorkflowState for node output caching
- ContextResolver for template variable resolution
"""

from agio.workflow.base import BaseWorkflow
from agio.workflow.condition import ConditionEvaluator
from agio.workflow.loop import LoopWorkflow
from agio.workflow.mapping import InputMapping
from agio.workflow.node import WorkflowNode
from agio.workflow.parallel import ParallelWorkflow
from agio.workflow.pipeline import PipelineWorkflow
from agio.workflow.resolver import ContextResolver
from agio.workflow.runnable_tool import (
    DEFAULT_MAX_DEPTH,
    CircularReferenceError,
    MaxDepthExceededError,
    RunnableTool,
    as_tool,
)
from agio.workflow.state import WorkflowState

__all__ = [
    # Core
    "InputMapping",
    "ConditionEvaluator",
    "WorkflowNode",
    # State management
    "WorkflowState",
    "ContextResolver",
    # Workflow types
    "BaseWorkflow",
    "PipelineWorkflow",
    "LoopWorkflow",
    "ParallelWorkflow",
    # Runnable as Tool
    "RunnableTool",
    "as_tool",
    "CircularReferenceError",
    "MaxDepthExceededError",
    "DEFAULT_MAX_DEPTH",
]
