"""
Run management routes.
"""

from fastapi import APIRouter, HTTPException, Depends
from agio.api.schemas.common import PaginatedResponse, SuccessResponse
from agio.api.dependencies import get_repository
from agio.execution import get_execution_controller
from agio.db.repository import AgentRunRepository
from agio.utils.logging import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)

router = APIRouter(prefix="/api/runs", tags=["Runs"])


class RunResponse(BaseModel):
    """Run response schema."""
    id: str
    agent_id: str
    user_id: str | None
    session_id: str | None
    status: str
    input_query: str
    response_content: str | None
    metrics: dict
    created_at: str



@router.get("", response_model=PaginatedResponse[RunResponse])
async def list_runs(
    agent_id: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    repository: AgentRunRepository = Depends(get_repository),
):
    """List runs with filtering."""
    try:
        runs = await repository.list_runs(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        # Convert to response format
        items = []
        for run in runs:
            # Apply additional filters  
            if agent_id and run.agent_id != agent_id:
                continue
            if status and run.status.value != status:
                continue
                
            items.append(RunResponse(
                id=run.id,
                agent_id=run.agent_id,
                user_id=run.user_id,
                session_id=run.session_id,
                status=run.status.value,
                input_query=run.input_query,
                response_content=run.response_content,
                metrics={
                    "total_tokens": run.metrics.total_tokens,
                    "duration": run.metrics.duration,
                    "total_steps": len(run.steps)
                },
                created_at=run.created_at.isoformat() if run.created_at else ""
            ))
        
        logger.info("runs_listed", count=len(items))
        
        return PaginatedResponse(
            total=len(items),
            items=items,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error("list_runs_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list runs: {str(e)}")


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    repository: AgentRunRepository = Depends(get_repository),
):
    """Get run by ID."""
    try:
        run = await repository.get_run(run_id)
        
        if not run:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        
        logger.info("run_retrieved", run_id=run_id)
        
        return RunResponse(
            id=run.id,
            agent_id=run.agent_id,
            user_id=run.user_id,
            session_id=run.session_id,
            status=run.status.value,
            input_query=run.input_query,
            response_content=run.response_content,
            metrics={
                "total_tokens": run.metrics.total_tokens,
                "duration": run.metrics.duration,
                "total_steps": len(run.steps)
            },
            created_at=run.created_at.isoformat() if run.created_at else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_run_failed", run_id=run_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get run: {str(e)}")


@router.post("/{run_id}/pause", response_model=SuccessResponse)
async def pause_run(run_id: str):
    """Pause a running execution."""
    controller = get_execution_controller()
    
    if controller.pause_run(run_id):
        return SuccessResponse(message=f"Run '{run_id}' paused successfully")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause run '{run_id}'"
        )


@router.post("/{run_id}/resume", response_model=SuccessResponse)
async def resume_run(run_id: str):
    """Resume a paused execution."""
    controller = get_execution_controller()
    
    if controller.resume_run(run_id):
        return SuccessResponse(message=f"Run '{run_id}' resumed successfully")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume run '{run_id}'"
        )


@router.post("/{run_id}/cancel", response_model=SuccessResponse)
async def cancel_run(run_id: str):
    """Cancel a running execution."""
    controller = get_execution_controller()
    
    if controller.cancel_run(run_id):
        return SuccessResponse(message=f"Run '{run_id}' cancelled successfully")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run '{run_id}'"
        )
