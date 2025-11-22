"""
Checkpoint management routes.
"""

from fastapi import APIRouter, HTTPException
from agio.api.schemas.common import PaginatedResponse, SuccessResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/checkpoints", tags=["Checkpoints"])


class CheckpointResponse(BaseModel):
    """Checkpoint response schema."""
    id: str
    run_id: str
    step_num: int
    description: str | None
    created_at: str
    message_count: int
    total_tokens: int


class CheckpointCreateRequest(BaseModel):
    """Checkpoint creation request."""
    description: str | None = None
    tags: list[str] = []


class RestoreRequest(BaseModel):
    """Restore from checkpoint request."""
    create_new_run: bool = True
    modifications: dict | None = None


@router.get("/runs/{run_id}/checkpoints", response_model=PaginatedResponse[CheckpointResponse])
async def list_checkpoints(
    run_id: str,
    limit: int = 20,
    offset: int = 0
):
    """List checkpoints for a run."""
    # TODO: Implement with CheckpointManager
    return PaginatedResponse(
        total=0,
        items=[],
        limit=limit,
        offset=offset
    )


@router.post("/runs/{run_id}/checkpoints", response_model=SuccessResponse, status_code=201)
async def create_checkpoint(run_id: str, request: CheckpointCreateRequest):
    """Create a checkpoint for a run."""
    # TODO: Implement with CheckpointManager
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{checkpoint_id}", response_model=CheckpointResponse)
async def get_checkpoint(checkpoint_id: str):
    """Get checkpoint by ID."""
    # TODO: Implement with CheckpointManager
    raise HTTPException(status_code=404, detail=f"Checkpoint '{checkpoint_id}' not found")


@router.post("/{checkpoint_id}/restore", response_model=SuccessResponse)
async def restore_checkpoint(checkpoint_id: str, request: RestoreRequest):
    """Restore execution from checkpoint."""
    # TODO: Implement with ResumeRunner
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/{checkpoint_id}/fork", response_model=SuccessResponse)
async def fork_checkpoint(checkpoint_id: str, request: RestoreRequest):
    """Fork execution from checkpoint."""
    # TODO: Implement with ForkManager
    raise HTTPException(status_code=501, detail="Not implemented yet")
