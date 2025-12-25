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

from agio.config import ConfigSystem, get_config_system
from agio.api.deps import get_session_store, get_trace_store
from agio.domain import StepEventType
from agio.runtime import Wire, RunnableExecutor
from agio.runtime.protocol import ExecutionContext

router = APIRouter(prefix="/runnables")


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

    for name, instance in instances.items():
        # Check if it has the Runnable protocol
        if hasattr(instance, "run") and hasattr(instance, "id"):
            info = RunnableInfo(
                id=instance.id,
                type=type(instance).__name__,
            )
            # Categorize
            if type(instance).__name__ in ("PipelineWorkflow", "LoopWorkflow", "ParallelWorkflow"):
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
        instance = config_system.get_instance(runnable_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Runnable not found: {runnable_id}")

    info = {
        "id": instance.id,
        "type": type(instance).__name__,
    }

    # Add workflow-specific info
    if hasattr(instance, "stages"):
        info["stages"] = [
            {
                "id": stage.id,
                "runnable": stage.runnable if isinstance(stage.runnable, str) else stage.runnable.id,
                "input_template": stage.input,
                "condition": stage.condition,
            }
            for stage in instance.stages
        ]

    if hasattr(instance, "condition") and hasattr(instance, "max_iterations"):
        info["loop_condition"] = instance.condition
        info["max_iterations"] = instance.max_iterations

    if hasattr(instance, "merge_template"):
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
        instance = config_system.get_instance(runnable_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Runnable not found: {runnable_id}")

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
        # Create Session-level resources at API entry point
        wire = Wire()
        session_store = get_session_store(config_sys=config_system)
        run_id = str(uuid4())

        # Use runnable_type property from Runnable protocol
        runnable_type = instance.runnable_type

        # Create context with wire
        context = ExecutionContext(
            run_id=run_id,
            wire=wire,
            session_id=request.session_id or str(uuid4()),
            user_id=request.user_id,
            runnable_type=runnable_type,
            runnable_id=instance.id,
        )

        # Initialize trace collector
        from agio.observability.collector import create_collector

        store = get_trace_store(config_sys=config_system)
        collector = create_collector(store)

        # Create RunnableExecutor
        executor = RunnableExecutor(store=session_store)

        # Start execution in background task using RunnableExecutor
        async def _run():
            try:
                await executor.execute(instance, query, context)
            finally:
                await wire.close()

        task = asyncio.create_task(_run())

        try:
            # Consume events from wire through collector
            async for event in collector.wrap_stream(
                wire.read(),
                trace_id=None,  # Will be generated
                workflow_id=instance.id if hasattr(instance, "stages") else None,
                agent_id=instance.id if not hasattr(instance, "stages") else None,
                session_id=context.session_id,
                user_id=context.user_id,
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
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return EventSourceResponse(
        event_generator(),
        headers={
            "Connection": "close",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_non_streaming(
    instance: Any,
    query: str,
    session_id: str | None,
    user_id: str | None,
    config_system: ConfigSystem,
) -> dict[str, Any]:
    """Non-streaming execution using Wire."""
    # Create Session-level resources
    wire = Wire()
    session_store = get_session_store(config_sys=config_system)
    run_id = str(uuid4())

    # Use runnable_type property from Runnable protocol
    runnable_type = instance.runnable_type
    
    context = ExecutionContext(
        run_id=run_id,
        wire=wire,
        session_id=session_id or str(uuid4()),
        user_id=user_id,
        runnable_type=runnable_type,
        runnable_id=instance.id,
    )

    # Initialize trace collector
    from agio.observability.collector import create_collector

    store = get_trace_store(config_sys=config_system)
    collector = create_collector(store)

    response_content = ""
    # In ExecutionContext model, run_id is known upfront
    final_run_id = run_id
    session_id_final = context.session_id
    metrics = {}

    # Get session store from ConfigSystem (no reflection)
    session_store = get_session_store(config_sys=config_system)
    executor = RunnableExecutor(store=session_store)

    async def _run():
        try:
            return await executor.execute(instance, query, context)
        finally:
            await wire.close()

    task = asyncio.create_task(_run())

    try:
        # Wrap the stream with collector to ensure traces are saved
        async for event in collector.wrap_stream(
            wire.read(),
            trace_id=None,
            workflow_id=instance.id if hasattr(instance, "stages") else None,
            agent_id=instance.id if not hasattr(instance, "stages") else None,
            session_id=context.session_id,
            user_id=context.user_id,
            input_query=query,
        ):
            if event.type == StepEventType.RUN_STARTED:
                # RUN_STARTED event should match our generated run_id
                pass

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

    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return {
        "run_id": final_run_id,
        "session_id": session_id_final,
        "response": response_content,
        "metrics": metrics,
    }
