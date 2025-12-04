"""
Runnable API routes - unified API for Agent and Workflow execution.

Provides a unified interface for running any Runnable (Agent or Workflow)
through the same endpoint.
"""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.config import ConfigSystem, get_config_system
from agio.workflow import RunContext, WorkflowEngine

router = APIRouter(prefix="/runnables")


class RunRequest(BaseModel):
    """Request body for running a Runnable."""

    query: str
    session_id: str | None = None
    user_id: str | None = None


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

    Returns a Server-Sent Events stream of execution events.
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

    async def event_generator():
        context = RunContext(
            session_id=request.session_id or str(uuid4()),
            user_id=request.user_id,
            trace_id=str(uuid4()),
        )

        try:
            async for event in instance.run(request.query, context=context):
                yield {
                    "event": event.type.value,
                    "data": event.model_dump_json(),
                }
        except Exception as e:
            yield {
                "event": "error",
                "data": f'{{"error": "{str(e)}"}}',
            }

    return EventSourceResponse(event_generator())
