"""
Runnable API routes - unified API for Agent execution.

Provides a unified interface for running any Runnable (Agent)
through the same endpoint.
"""

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.api.deps import get_session_store, get_trace_store
from agio.config import ConfigSystem, get_config_system
from agio.runtime import Runnable, RunnableExecutor
from agio.runtime.protocol import RunnableType

router = APIRouter(prefix="/runnables")

CLEANUP_TIMEOUT_SECONDS = 5.0


class RunRequest(BaseModel):
    """Request body for running a Runnable."""

    query: str | None = None
    message: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    stream: bool = True


class RunnableInfo(BaseModel):
    """Information about a Runnable."""

    id: str
    type: str
    description: str | None = None


@router.get("")
async def list_runnables(
    config_system: ConfigSystem = Depends(get_config_system),
) -> dict[str, list[RunnableInfo]]:
    """List all available Runnables (Agents)."""
    agents = []
    instances = config_system.get_all_instances()

    for _, instance in instances.items():
        if hasattr(instance, "run") and hasattr(instance, "id"):
            if isinstance(instance, Runnable):
                info = RunnableInfo(
                    id=instance.id,
                    type=type(instance).__name__,
                )
                agents.append(info)

    return {"agents": agents}


@router.get("/{runnable_id}")
async def get_runnable_info(
    runnable_id: str,
    config_system: ConfigSystem = Depends(get_config_system),
) -> dict[str, Any]:
    """Get information about a specific Runnable."""
    try:
        instance: Runnable = config_system.get_instance(runnable_id)
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Runnable not found: {runnable_id}"
        )

    return {
        "id": instance.id,
        "type": type(instance).__name__,
    }


@router.post("/{runnable_id}/run")
async def run_runnable(
    runnable_id: str,
    request: RunRequest,
    config_system: ConfigSystem = Depends(get_config_system),
    session_store=Depends(get_session_store),
    trace_store=Depends(get_trace_store),
):
    """Execute a Runnable (Agent)."""
    try:
        instance: Runnable = config_system.get_instance(runnable_id)
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Runnable not found: {runnable_id}"
        )

    if not hasattr(instance, "run"):
        raise HTTPException(
            status_code=400,
            detail=f"Component {runnable_id} does not implement Runnable protocol",
        )

    input_text = request.query or request.message or ""
    session_id = request.session_id or str(uuid4())

    executor = RunnableExecutor(store=session_store, trace_store=trace_store)

    async def execute_and_stream():
        try:
            async for event in executor.execute_stream(
                instance,
                input_text,
                session_id=session_id,
                user_id=request.user_id,
            ):
                yield {"event": event.type.value, "data": event.model_dump_json()}
        except Exception as e:
            yield {"event": "error", "data": str(e)}

    if request.stream:
        return EventSourceResponse(execute_and_stream())
    else:
        events = []
        async for event in execute_and_stream():
            events.append(event)
        return {"events": events}
