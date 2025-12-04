"""
Workflow-specific API routes.

Provides endpoints for workflow management and visualization.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agio.config import ConfigSystem, get_config_system
from agio.workflow import BaseWorkflow, LoopWorkflow, ParallelWorkflow

router = APIRouter(prefix="/workflows")


class WorkflowSummary(BaseModel):
    """Summary information about a workflow."""

    id: str
    type: str
    stage_count: int


class StageInfo(BaseModel):
    """Information about a workflow stage."""

    id: str
    runnable: str
    input_template: str
    condition: str | None = None


class WorkflowStructure(BaseModel):
    """Complete structure of a workflow."""

    id: str
    type: str
    stages: list[StageInfo]
    # Loop specific
    loop_condition: str | None = None
    max_iterations: int | None = None
    # Parallel specific
    merge_template: str | None = None


@router.get("")
async def list_workflows(
    config_system: ConfigSystem = Depends(get_config_system),
) -> list[WorkflowSummary]:
    """
    List all available workflows.
    """
    workflows = []

    instances = config_system.get_all_instances()

    for name, instance in instances.items():
        if isinstance(instance, BaseWorkflow):
            workflows.append(
                WorkflowSummary(
                    id=instance.id,
                    type=type(instance).__name__,
                    stage_count=len(instance.stages),
                )
            )

    return workflows


@router.get("/{workflow_id}")
async def get_workflow_structure(
    workflow_id: str,
    config_system: ConfigSystem = Depends(get_config_system),
) -> WorkflowStructure:
    """
    Get the complete structure of a workflow.

    Useful for frontend visualization.
    """
    try:
        instance = config_system.get_instance(workflow_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")

    if not isinstance(instance, BaseWorkflow):
        raise HTTPException(
            status_code=400,
            detail=f"Component {workflow_id} is not a Workflow",
        )

    stages = [
        StageInfo(
            id=stage.id,
            runnable=stage.runnable if isinstance(stage.runnable, str) else stage.runnable.id,
            input_template=stage.input,
            condition=stage.condition,
        )
        for stage in instance.stages
    ]

    structure = WorkflowStructure(
        id=instance.id,
        type=type(instance).__name__,
        stages=stages,
    )

    # Add type-specific fields
    if isinstance(instance, LoopWorkflow):
        structure.loop_condition = instance.condition
        structure.max_iterations = instance.max_iterations
    elif isinstance(instance, ParallelWorkflow):
        structure.merge_template = instance.merge_template

    return structure


@router.get("/{workflow_id}/dependencies")
async def get_workflow_dependencies(
    workflow_id: str,
    config_system: ConfigSystem = Depends(get_config_system),
) -> dict[str, list[str]]:
    """
    Get the dependency graph of a workflow.

    Shows which stages depend on which other stages based on input templates.
    """
    try:
        instance = config_system.get_instance(workflow_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")

    if not isinstance(instance, BaseWorkflow):
        raise HTTPException(
            status_code=400,
            detail=f"Component {workflow_id} is not a Workflow",
        )

    dependencies: dict[str, list[str]] = {}

    for stage in instance.stages:
        deps = stage.get_dependencies()
        # Filter to only include other stage IDs (not 'query' or 'loop')
        stage_ids = {s.id for s in instance.stages}
        stage_deps = [d for d in deps if d in stage_ids]
        dependencies[stage.id] = stage_deps

    return dependencies
