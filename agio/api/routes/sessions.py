"""
Session management routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agio.api.deps import get_config_sys, get_repository
from agio.config import ConfigSystem
from agio.providers.storage import AgentRunRepository

router = APIRouter(prefix="/sessions")


# Response Models
class RunResponse(BaseModel):
    id: str
    agent_id: str
    user_id: str | None
    session_id: str | None
    status: str
    input_query: str
    response_content: str | None
    created_at: str


class StepResponse(BaseModel):
    id: str
    session_id: str
    sequence: int
    role: str
    content: str | None
    tool_calls: list[dict] | None = None
    created_at: str


class SessionResponse(BaseModel):
    session_id: str
    runs: list[RunResponse]
    step_count: int


class PaginatedRuns(BaseModel):
    total: int
    items: list[RunResponse]
    limit: int
    offset: int


# Routes
@router.get("")
async def list_sessions(
    user_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    repository: AgentRunRepository = Depends(get_repository),
) -> PaginatedRuns:
    """List all sessions (runs)."""
    runs = await repository.list_runs(user_id=user_id, limit=limit, offset=offset)

    items = [
        RunResponse(
            id=run.id,
            agent_id=run.agent_id,
            user_id=run.user_id,
            session_id=run.session_id,
            status=run.status.value,
            input_query=run.input_query,
            response_content=run.response_content,
            created_at=run.created_at.isoformat() if run.created_at else "",
        )
        for run in runs
    ]

    return PaginatedRuns(total=len(items), items=items, limit=limit, offset=offset)


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    repository: AgentRunRepository = Depends(get_repository),
) -> SessionResponse:
    """Get session details."""
    runs = await repository.list_runs(session_id=session_id, limit=100)

    if not runs:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    step_count = await repository.get_step_count(session_id)

    return SessionResponse(
        session_id=session_id,
        runs=[
            RunResponse(
                id=run.id,
                agent_id=run.agent_id,
                user_id=run.user_id,
                session_id=run.session_id,
                status=run.status.value,
                input_query=run.input_query,
                response_content=run.response_content,
                created_at=run.created_at.isoformat() if run.created_at else "",
            )
            for run in runs
        ],
        step_count=step_count,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    repository: AgentRunRepository = Depends(get_repository),
):
    """Delete a session and all its data."""
    # Delete all runs in session
    runs = await repository.list_runs(session_id=session_id, limit=1000)
    for run in runs:
        await repository.delete_run(run.id)

    # Delete all steps
    await repository.delete_steps(session_id, start_seq=0)


@router.get("/{session_id}/runs")
async def get_session_runs(
    session_id: str,
    limit: int = 20,
    offset: int = 0,
    repository: AgentRunRepository = Depends(get_repository),
) -> PaginatedRuns:
    """Get runs for a session."""
    runs = await repository.list_runs(session_id=session_id, limit=limit, offset=offset)

    items = [
        RunResponse(
            id=run.id,
            agent_id=run.agent_id,
            user_id=run.user_id,
            session_id=run.session_id,
            status=run.status.value,
            input_query=run.input_query,
            response_content=run.response_content,
            created_at=run.created_at.isoformat() if run.created_at else "",
        )
        for run in runs
    ]

    return PaginatedRuns(total=len(items), items=items, limit=limit, offset=offset)


@router.get("/{session_id}/steps")
async def get_session_steps(
    session_id: str,
    limit: int = 100,
    repository: AgentRunRepository = Depends(get_repository),
) -> list[StepResponse]:
    """Get all steps for a session."""
    steps = await repository.get_steps(session_id, limit=limit)

    return [
        StepResponse(
            id=step.id,
            session_id=step.session_id,
            sequence=step.sequence,
            role=step.role.value,
            content=step.content,
            tool_calls=step.tool_calls,
            created_at=step.created_at.isoformat() if step.created_at else "",
        )
        for step in steps
    ]
