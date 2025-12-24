"""
Runtime module - Common runtime infrastructure.

This module contains:
- RunnableExecutor: Unified Run lifecycle management for all Runnable types
- ResumeExecutor: Unified Session Resume mechanism for Agent and Workflow
- Wire: Event streaming channel
- EventFactory: Context-bound event factory
"""

from agio.runtime.runnable_executor import RunnableExecutor
from agio.runtime.resume_executor import ResumeExecutor
from agio.runtime.wire import Wire
from agio.runtime.event_factory import EventFactory
from agio.runtime.control import AbortSignal, fork_session
from agio.runtime.sequence_manager import SequenceManager
from agio.runtime.step_repository import StepRepository
from agio.runtime.protocol import Runnable, RunOutput, ExecutionContext

__all__ = [
    "RunnableExecutor",
    "ResumeExecutor",
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
