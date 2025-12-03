"""
LLM Logs API endpoints for querying and streaming LLM call logs.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.observability.models import LLMCallLog, LLMLogQuery
from agio.observability.store import get_llm_log_store
from agio.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/llm")


class LLMLogListResponse(BaseModel):
    """Response for listing LLM logs."""

    total: int
    items: list[LLMCallLog]
    limit: int
    offset: int


@router.get("/logs", response_model=LLMLogListResponse)
async def list_llm_logs(
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    run_id: Optional[str] = Query(None, description="Filter by run ID"),
    model_id: Optional[str] = Query(None, description="Filter by model ID"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of logs"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List LLM call logs with optional filters.

    **Query Parameters:**
    - `agent_name`: Filter by agent name
    - `session_id`: Filter by session ID
    - `run_id`: Filter by run ID
    - `model_id`: Filter by model ID (e.g., openai/gpt-4o)
    - `provider`: Filter by provider (openai/anthropic/deepseek)
    - `status`: Filter by status (running/completed/error)
    - `start_time`: Filter logs after this time
    - `end_time`: Filter logs before this time
    - `limit`: Maximum number of logs to return (default: 50)
    - `offset`: Offset for pagination (default: 0)

    **Returns:** Paginated list of LLM call logs
    """
    store = get_llm_log_store()

    query = LLMLogQuery(
        agent_name=agent_name,
        session_id=session_id,
        run_id=run_id,
        model_id=model_id,
        provider=provider,
        status=status,  # type: ignore
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    logs = await store.query(query)
    total = await store.count(query)

    return LLMLogListResponse(
        total=total,
        items=logs,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/{log_id}", response_model=LLMCallLog)
async def get_llm_log(log_id: str):
    """
    Get a specific LLM call log by ID.

    **Path Parameters:**
    - `log_id`: The unique log ID

    **Returns:** The LLM call log details
    """
    store = get_llm_log_store()

    # Query by ID
    query = LLMLogQuery(limit=500)
    logs = await store.query(query)

    for log in logs:
        if log.id == log_id:
            return log

    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail=f"Log '{log_id}' not found")


@router.get("/logs/stream")
async def stream_llm_logs(
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    run_id: Optional[str] = Query(None, description="Filter by run ID"),
):
    """
    Stream LLM call logs in real-time via Server-Sent Events (SSE).

    **Query Parameters:**
    - `agent_name`: Filter by agent name (optional)
    - `session_id`: Filter by session ID (optional)
    - `run_id`: Filter by run ID (optional)

    **Returns:** SSE stream of LLM call log events
    """
    store = get_llm_log_store()
    queue = store.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    log = await asyncio.wait_for(queue.get(), timeout=30.0)

                    # Apply filters
                    if agent_name and log.agent_name != agent_name:
                        continue
                    if session_id and log.session_id != session_id:
                        continue
                    if run_id and log.run_id != run_id:
                        continue

                    yield {
                        "event": "llm_call",
                        "data": log.model_dump_json(),
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "keepalive", "data": ""}
        finally:
            store.unsubscribe(queue)

    return EventSourceResponse(event_generator())


@router.get("/stats")
async def get_llm_stats(
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
):
    """
    Get aggregated LLM call statistics.

    **Query Parameters:**
    - `agent_name`: Filter by agent name (optional)
    - `start_time`: Start time filter (optional)
    - `end_time`: End time filter (optional)

    **Returns:** Aggregated statistics
    """
    store = get_llm_log_store()

    # Get all matching logs
    query = LLMLogQuery(
        agent_name=agent_name,
        start_time=start_time,
        end_time=end_time,
        limit=500,
    )
    logs = await store.query(query)

    # Calculate stats
    total_calls = len(logs)
    completed_calls = sum(1 for log in logs if log.status == "completed")
    error_calls = sum(1 for log in logs if log.status == "error")
    running_calls = sum(1 for log in logs if log.status == "running")

    total_tokens = sum(log.total_tokens or 0 for log in logs)
    total_input_tokens = sum(log.input_tokens or 0 for log in logs)
    total_output_tokens = sum(log.output_tokens or 0 for log in logs)

    durations = [log.duration_ms for log in logs if log.duration_ms is not None]
    avg_duration_ms = sum(durations) / len(durations) if durations else 0

    first_token_times = [
        log.first_token_ms for log in logs if log.first_token_ms is not None
    ]
    avg_first_token_ms = (
        sum(first_token_times) / len(first_token_times) if first_token_times else 0
    )

    # Provider breakdown
    provider_counts: dict[str, int] = {}
    for log in logs:
        provider_counts[log.provider] = provider_counts.get(log.provider, 0) + 1

    return {
        "total_calls": total_calls,
        "completed_calls": completed_calls,
        "error_calls": error_calls,
        "running_calls": running_calls,
        "success_rate": completed_calls / total_calls if total_calls > 0 else 0,
        "total_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "avg_duration_ms": avg_duration_ms,
        "avg_first_token_ms": avg_first_token_ms,
        "provider_breakdown": provider_counts,
    }


__all__ = ["router"]
