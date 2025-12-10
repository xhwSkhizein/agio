"""
LLM Call Tracker - Wraps Model.arun_stream to track all LLM calls.
"""

import asyncio
import contextvars
import time
from typing import TYPE_CHECKING, Any, AsyncIterator
from uuid import uuid4

from agio.observability.models import LLMCallLog
from agio.observability.store import get_llm_log_store
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.providers.llm.base import Model, StreamChunk

logger = get_logger(__name__)

# Context variables for tracking metadata
_current_agent_name: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_agent_name", default=None
)
_current_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_session_id", default=None
)
_current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_run_id", default=None
)

# Global tracker instance
_tracker: "LLMCallTracker | None" = None


def set_tracking_context(
    agent_name: str | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
) -> None:
    """Set context variables for LLM call tracking."""
    if agent_name is not None:
        _current_agent_name.set(agent_name)
    if session_id is not None:
        _current_session_id.set(session_id)
    if run_id is not None:
        _current_run_id.set(run_id)


def clear_tracking_context() -> None:
    """Clear tracking context."""
    _current_agent_name.set(None)
    _current_session_id.set(None)
    _current_run_id.set(None)


class LLMCallTracker:
    """
    Tracks all LLM calls by wrapping Model.arun_stream.

    Usage:
        tracker = LLMCallTracker()
        await tracker.initialize()

        # Wrap a model
        tracker.wrap_model(model)

        # Or use context manager for tracking context
        with tracker.tracking_context(agent_name="my_agent", run_id="123"):
            async for chunk in model.arun_stream(messages):
                ...
    """

    def __init__(self):
        self._store = get_llm_log_store()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the tracker and store."""
        if self._initialized:
            return
        await self._store.initialize()
        self._initialized = True

    def wrap_model(self, model: "Model") -> None:
        """
        Wrap a Model instance to track its arun_stream calls.

        This replaces the model's arun_stream method with a tracked version.
        """
        original_arun_stream = model.arun_stream

        async def tracked_arun_stream(
            messages: list[dict], tools: list[dict] | None = None
        ) -> AsyncIterator["StreamChunk"]:
            async for chunk in self._track_call(model, original_arun_stream, messages, tools):
                yield chunk

        # Replace the method
        model.arun_stream = tracked_arun_stream  # type: ignore

    async def _track_call(
        self,
        model: "Model",
        original_fn,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> AsyncIterator["StreamChunk"]:
        """Track a single LLM call."""
        # Determine provider from model class
        provider = self._get_provider(model)

        # Build request params dict
        request_params = self._build_request_params(model, messages, tools)

        # Create log entry
        log = LLMCallLog(
            id=str(uuid4()),
            agent_name=_current_agent_name.get(),
            session_id=_current_session_id.get(),
            run_id=_current_run_id.get(),
            model_id=model.id,
            model_name=getattr(model, "model_name", None),
            provider=provider,
            request=request_params,
            messages=messages,
            tools=tools,
            status="running",
        )

        # Record start
        await self._store.add(log)
        start_time = time.time()
        first_token_time: float | None = None

        # Accumulate response
        content_parts: list[str] = []
        # Use dict to merge streaming tool_calls by index
        tool_calls_map: dict[int, dict] = {}
        usage_data: dict[str, int] | None = None

        try:
            async for chunk in original_fn(messages, tools):
                # Track first token time
                if first_token_time is None and (chunk.content or chunk.tool_calls):
                    first_token_time = time.time()

                # Accumulate content
                if chunk.content:
                    content_parts.append(chunk.content)

                # Merge streaming tool calls by index
                if chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_map:
                            # Initialize new tool call entry
                            tool_calls_map[idx] = {
                                "id": tc.get("id", ""),
                                "type": tc.get("type", "function"),
                                "function": {
                                    "name": "",
                                    "arguments": "",
                                },
                            }
                        
                        # Update id if present (usually only in first chunk)
                        if tc.get("id"):
                            tool_calls_map[idx]["id"] = tc["id"]
                        
                        # Merge function data
                        if "function" in tc:
                            func = tc["function"]
                            if func.get("name"):
                                tool_calls_map[idx]["function"]["name"] += func["name"]
                            if func.get("arguments"):
                                tool_calls_map[idx]["function"]["arguments"] += func["arguments"]

                # Capture usage
                if chunk.usage:
                    usage_data = chunk.usage

                # Capture finish reason
                if chunk.finish_reason:
                    log.finish_reason = chunk.finish_reason

                yield chunk

            # Update log on completion
            end_time = time.time()
            log.status = "completed"
            log.response_content = "".join(content_parts) if content_parts else None
            # Convert merged tool_calls map to sorted list
            tool_calls = [tool_calls_map[i] for i in sorted(tool_calls_map.keys())] if tool_calls_map else None
            log.response_tool_calls = tool_calls
            log.duration_ms = (end_time - start_time) * 1000

            if first_token_time:
                log.first_token_ms = (first_token_time - start_time) * 1000

            if usage_data:
                log.input_tokens = usage_data.get("prompt_tokens")
                log.output_tokens = usage_data.get("completion_tokens")
                log.total_tokens = usage_data.get("total_tokens")

        except asyncio.CancelledError:
            # Handle cancellation - update log status to cancelled
            end_time = time.time()
            log.status = "cancelled"
            log.response_content = "".join(content_parts) if content_parts else None
            tool_calls = [tool_calls_map[i] for i in sorted(tool_calls_map.keys())] if tool_calls_map else None
            log.response_tool_calls = tool_calls
            log.duration_ms = (end_time - start_time) * 1000
            if first_token_time:
                log.first_token_ms = (first_token_time - start_time) * 1000
            await self._store.update(log)
            raise

        except Exception as e:
            # Update log on error
            end_time = time.time()
            log.status = "error"
            log.error = str(e)
            log.duration_ms = (end_time - start_time) * 1000
            await self._store.update(log)
            raise

        # Persist final state
        await self._store.update(log)

    def _get_provider(self, model: "Model") -> str:
        """Extract provider name from model."""
        class_name = model.__class__.__name__.lower()
        if "openai" in class_name:
            return "openai"
        elif "anthropic" in class_name:
            return "anthropic"
        elif "deepseek" in class_name:
            return "deepseek"
        else:
            return "unknown"

    def _build_request_params(
        self, model: "Model", messages: list[dict], tools: list[dict] | None
    ) -> dict[str, Any]:
        """Build request parameters dict for logging."""
        params: dict[str, Any] = {
            "model": getattr(model, "model_name", None) or model.name,
            "temperature": model.temperature,
            "top_p": model.top_p,
            "max_tokens": model.max_tokens,
            "messages_count": len(messages),
            "has_tools": tools is not None and len(tools) > 0,
        }

        # Add provider-specific params
        if hasattr(model, "frequency_penalty"):
            params["frequency_penalty"] = model.frequency_penalty
        if hasattr(model, "presence_penalty"):
            params["presence_penalty"] = model.presence_penalty

        return params


def get_tracker() -> LLMCallTracker:
    """Get the global tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = LLMCallTracker()
    return _tracker


__all__ = [
    "LLMCallTracker",
    "get_tracker",
    "set_tracking_context",
    "clear_tracking_context",
]
