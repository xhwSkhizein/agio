"""
Runtime module - Common runtime infrastructure.

This module contains:
- RunnableExecutor: Unified Run lifecycle management for all Runnable types
- ResumeExecutor: Unified Session Resume mechanism for Agent and Workflow
- Wire: Event streaming channel
- EventFactory: Context-bound event factory
"""

from agio.runtime.control import AbortSignal, fork_session
from agio.runtime.event_factory import EventFactory
from agio.runtime.protocol import ExecutionContext, Runnable, RunOutput
from agio.runtime.runnable_executor import RunnableExecutor
from agio.runtime.sequence_manager import SequenceManager
from agio.runtime.step_repository import StepRepository
from agio.runtime.wire import Wire

__all__ = [
    "RunnableExecutor",
    "Wire",
    "ExecutionContext",
    "EventFactory",
    "AbortSignal",
    "fork_session",
    "SequenceManager",
    "StepRepository",
    "Runnable",
    "RunOutput",
]
