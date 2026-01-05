"""
Runnable API routes - unified API for Agent and Workflow execution.

Provides a unified interface for running any Runnable (Agent or Workflow)
through the same endpoint.

Wire-based Architecture:
- Wire is created at API entry point
- Agent.run() writes events to wire
- API layer consumes wire.read() for SSE response
"""

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.api.deps import get_session_store, get_trace_store
from agio.config import ConfigSystem, get_config_system
from agio.domain import StepEventType
from agio.runtime import Runnable, RunnableExecutor, Wire
from agio.runtime.protocol import RunnableType
from agio.workflow.base import BaseWorkflow
from agio.workflow.loop import LoopWorkflow
from agio.workflow.parallel import ParallelWorkflow

router = APIRouter(prefix="/runnables")

CLEANUP_TIMEOUT_SECONDS = 5.0


class RunRequest(BaseModel):
    """Request body for running a Runnable."""

    query: str | None = None
    message: str | None = None  # Alias for query (backward compatibility)
    session_id: str | None = None
    user_id: str | None = None
    stream: bool = True  # Support non-streaming mode


class RunnableInfo(BaseModel):
    """Information about a Runnable."""

    id: str
    type: str
    description: str | None = None


@router.get("")
async def list_runnables(
    config_system: ConfigSystem = Depends(get_config_system),
) -> dict[str, list[RunnableInfo]]:
    """
    List all available Runnables (Agents and Workflows).
    """
    agents = []
    workflows = []

    # Get all instances from config system
    instances = config_system.get_all_instances()

    for _, instance in instances.items():
        # Check if it has the Runnable protocol
        if hasattr(instance, "run") and hasattr(instance, "id"):
            info = RunnableInfo(
                id=instance.id,
                type=type(instance).__name__,
            )
            # Categorize using runnable_type enum
            if isinstance(instance, Runnable):
                if instance.runnable_type == RunnableType.WORKFLOW:
                    workflows.append(info)
                else:
                    agents.append(info)

    return {"agents": agents, "workflows": workflows}


@router.get("/{runnable_id}")
async def get_runnable_info(
    runnable_id: str,
    config_system: ConfigSystem = Depends(get_config_system),
) -> dict[str, Any]:
    """
    Get information about a specific Runnable.
    """
    try:
        instance: Runnable = config_system.get_instance(runnable_id)
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Runnable not found: {runnable_id}"
        )

    info = {
        "id": instance.id,
        "type": type(instance).__name__,
    }

    # Add workflow-specific info using type checking
    if isinstance(instance, BaseWorkflow):
        info["stages"] = [
            {
                "id": stage.id,
                "runnable": (
                    stage.runnable
                    if isinstance(stage.runnable, str)
                    else stage.runnable.id
                ),
                "input_template": stage.input_template,
                "condition": stage.condition,
            }
            for stage in instance.nodes
        ]

    # Add LoopWorkflow-specific info
    if isinstance(instance, LoopWorkflow):
        info["loop_condition"] = instance.condition
        info["max_iterations"] = instance.max_iterations

    # Add ParallelWorkflow-specific info
    if isinstance(instance, ParallelWorkflow):
        info["merge_template"] = instance.merge_template

    return info


@router.post("/{runnable_id}/run")
async def run_runnable(
    runnable_id: str,
    request: RunRequest,
    config_system: ConfigSystem = Depends(get_config_system),
):
    """
    Execute a Runnable (Agent or Workflow).

    Returns a Server-Sent Events stream of execution events (if stream=True),
    or a JSON response (if stream=False).

    Wire-based execution:
    1. Create Wire at API entry point
    2. Start runnable.run() in background task
    3. Consume wire.read() for SSE response or collect events for JSON response
    """
    try:
        instance: Runnable = config_system.get_instance(runnable_id)
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Runnable not found: {runnable_id}"
        )

    # Check if it implements Runnable protocol
    if not hasattr(instance, "run"):
        raise HTTPException(
            status_code=400,
            detail=f"Component {runnable_id} does not implement Runnable protocol",
        )

    # Get query from either query or message field
    query = request.query or request.message
    if not query:
        raise HTTPException(
            status_code=400,
            detail="Either 'query' or 'message' field is required",
        )

    # Non-streaming mode
    if not request.stream:
        return await _run_non_streaming(
            instance,
            query,
            request.session_id,
            request.user_id,
            config_system,
        )

    # Streaming mode
    async def event_generator():
        session_store = get_session_store(config_sys=config_system)
        runnable_type = instance.runnable_type

        # Initialize trace collector
        from agio.observability.collector import create_collector

        store = get_trace_store(config_sys=config_system)
        collector = create_collector(store)

        # Create RunnableExecutor
        executor = RunnableExecutor(store=session_store)

        # Use execute_with_wire() for simplified execution with Wire control
        wire = Wire()
        session_id = request.session_id or str(uuid4())

        async def _run():
            try:
                await executor.execute_with_wire(
                    instance,
                    query,
                    wire,
                    session_id=session_id,
                    user_id=request.user_id,
                )
            finally:
                await wire.close()

        task = asyncio.create_task(_run())

        try:
            # Consume events from wire through collector
            async for event in collector.wrap_stream(
                wire.read(),
                trace_id=None,  # Will be generated
                workflow_id=instance.id
                if runnable_type == RunnableType.WORKFLOW
                else None,
                agent_id=instance.id if runnable_type == RunnableType.AGENT else None,
                session_id=session_id,
                user_id=request.user_id,
                input_query=query,
            ):
                yield {
                    "event": event.type.value,
                    "data": event.model_dump_json(),
                }
        except Exception as e:
            import json

            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
        finally:
            # Ensure task is cleaned up
            if not task.done():
                await _cancel_task_with_timeout(task, CLEANUP_TIMEOUT_SECONDS)

    return EventSourceResponse(
        event_generator(),
        headers={
            "Connection": "close",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_non_streaming(
    instance: Runnable,
    query: str,
    session_id: str | None,
    user_id: str | None,
    config_system: ConfigSystem,
) -> dict[str, Any]:
    """Non-streaming execution using Wire."""
    session_store = get_session_store(config_sys=config_system)
    runnable_type = instance.runnable_type
    session_id_final = session_id or str(uuid4())

    # Initialize trace collector
    from agio.observability.collector import create_collector

    store = get_trace_store(config_sys=config_system)
    collector = create_collector(store)

    # Create RunnableExecutor
    executor = RunnableExecutor(store=session_store)

    # Use execute_with_wire() for simplified execution
    wire = Wire()

    async def _run():
        try:
            return await executor.execute_with_wire(
                instance,
                query,
                wire,
                session_id=session_id_final,
                user_id=user_id,
            )
        finally:
            await wire.close()

    task = asyncio.create_task(_run())

    response_content = ""
    final_run_id: str | None = None
    metrics = {}

    try:
        # Wrap the stream with collector to ensure traces are saved
        async for event in collector.wrap_stream(
            wire.read(),
            trace_id=None,
            workflow_id=instance.id if runnable_type == RunnableType.WORKFLOW else None,
            agent_id=instance.id if runnable_type == RunnableType.AGENT else None,
            session_id=session_id_final,
            user_id=user_id,
            input_query=query,
        ):
            if event.type == StepEventType.RUN_STARTED:
                final_run_id = event.run_id

            elif event.type == StepEventType.STEP_DELTA:
                if event.delta and event.delta.content:
                    response_content += event.delta.content

            elif event.type == StepEventType.RUN_COMPLETED:
                if event.data and "metrics" in event.data:
                    metrics = event.data["metrics"]

        # Get final result
        result = await task
        if result.response and not response_content:
            response_content = result.response
        if not final_run_id and result.run_id:
            final_run_id = result.run_id

    finally:
        if not task.done():
            await _cancel_task_with_timeout(task, CLEANUP_TIMEOUT_SECONDS)

    return {
        "run_id": final_run_id or "unknown",
        "session_id": session_id_final,
        "response": response_content,
        "metrics": metrics,
    }


async def _cancel_task_with_timeout(task: asyncio.Task[Any], timeout: float) -> None:
    task.cancel()
    try:
        async with asyncio.timeout(timeout):
            await task
    except asyncio.CancelledError:
        pass
    except asyncio.TimeoutError:
        pass
