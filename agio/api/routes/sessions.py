"""
Session management routes.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.api.deps import get_config_sys, get_session_store
from agio.config import ConfigSystem
from agio.runtime import Wire, fork_session
from agio.runtime.resume_executor import ResumeExecutor
from agio.storage.session import SessionStore

router = APIRouter(prefix="/sessions")


# Response Models
class RunResponse(BaseModel):
    """Response model for a single agent run."""

    id: str
    agent_id: str
    user_id: str | None
    session_id: str | None
    status: str
    input_query: str
    response_content: str | None
    created_at: str


class StepResponse(BaseModel):
    """
    Response model for a conversation step.

    Different roles have different fields populated:
    - user: content only
    - assistant: content and/or tool_calls, reasoning_content, metrics
    - tool: name, tool_call_id, and content (tool result)
    """

    id: str
    session_id: str
    sequence: int
    role: str
    content: str | None
    reasoning_content: str | None = (
        None  # Reasoning content (e.g., DeepSeek thinking mode)
    )
    # Assistant step: list of tool calls to execute
    tool_calls: list[dict] | None = None
    # Tool step: name of the tool that was called
    name: str | None = None
    # Tool step: ID linking to the tool_call in assistant step
    tool_call_id: str | None = None
    created_at: str
    # Hierarchy fields for building execution tree
    run_id: str | None = None
    parent_run_id: str | None = None
    runnable_id: str | None = None
    runnable_type: str | None = None  # "agent"
    depth: int = 0
    # Metrics (for assistant and tool steps)
    metrics: dict | None = None


class SessionResponse(BaseModel):
    """Response model for a session with its runs and step count."""

    session_id: str
    runs: list[RunResponse]
    step_count: int


class PaginatedRuns(BaseModel):
    """Paginated response model for runs list."""

    total: int
    items: list[RunResponse]
    limit: int
    offset: int


class SessionSummary(BaseModel):
    """Aggregated session summary for display."""

    session_id: str
    agent_id: str | None
    user_id: str | None
    run_count: int
    step_count: int
    last_message: str | None
    last_activity: str
    status: str


class PaginatedSessionSummaries(BaseModel):
    """Paginated response model for session summaries list."""

    total: int
    items: list[SessionSummary]
    limit: int
    offset: int


class PaginatedSteps(BaseModel):
    """Paginated response model for steps list."""

    total: int
    items: list[dict]  # Using dict to allow exclude_none serialization
    limit: int
    offset: int


# Routes
@router.get("/summary")
async def list_session_summaries(
    user_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session_store: SessionStore = Depends(get_session_store),
) -> PaginatedSessionSummaries:
    """
    List aggregated session summaries.

    Groups runs by session_id and returns session-level metadata
    including run count, step count, and last activity.
    """
    # Get all runs (we'll aggregate by session_id)
    runs = await session_store.list_runs(user_id=user_id, limit=500, offset=0)

    # Aggregate by session_id
    session_map: dict[str, dict] = {}
    for run in runs:
        sid = run.session_id
        if not sid:
            continue

        if sid not in session_map:
            session_map[sid] = {
                "session_id": sid,
                "agent_id": run.runnable_id if run.runnable_type == "agent" else None,
                "user_id": run.user_id,
                "runs": [],
                "last_activity": run.created_at,
                "status": run.status.value,
            }

        session_map[sid]["runs"].append(run)
        # Update last activity if this run is more recent
        if run.created_at and (
            not session_map[sid]["last_activity"]
            or run.created_at > session_map[sid]["last_activity"]
        ):
            session_map[sid]["last_activity"] = run.created_at
            session_map[sid]["status"] = run.status.value

    # Build summaries with step counts
    summaries: list[SessionSummary] = []
    for sid, data in session_map.items():
        step_count = await session_store.get_step_count(sid)

        # Get last user message as preview
        steps = await session_store.get_steps(sid, limit=1)
        last_message = steps[0].content if steps else None

        summaries.append(
            SessionSummary(
                session_id=sid,
                agent_id=data["agent_id"],
                user_id=data["user_id"],
                run_count=len(data["runs"]),
                step_count=step_count,
                last_message=last_message[:100] if last_message else None,
                last_activity=data["last_activity"].isoformat()
                if data["last_activity"]
                else "",
                status=data["status"],
            )
        )

    # Sort by last activity (most recent first)
    summaries.sort(key=lambda x: x.last_activity, reverse=True)

    # Apply pagination
    total = len(summaries)
    summaries = summaries[offset : offset + limit]

    return PaginatedSessionSummaries(
        total=total,
        items=summaries,
        limit=limit,
        offset=offset,
    )


@router.get("")
async def list_sessions(
    user_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session_store: SessionStore = Depends(get_session_store),
) -> PaginatedRuns:
    """List all sessions (runs)."""
    runs = await session_store.list_runs(user_id=user_id, limit=limit, offset=offset)

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
    session_store: SessionStore = Depends(get_session_store),
) -> SessionResponse:
    """Get session details."""
    runs = await session_store.list_runs(session_id=session_id, limit=100)

    if not runs:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    step_count = await session_store.get_step_count(session_id)

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
    session_store: SessionStore = Depends(get_session_store),
):
    """Delete a session and all its data."""
    # Delete all runs in session
    runs = await session_store.list_runs(session_id=session_id, limit=1000)
    for run in runs:
        await session_store.delete_run(run.id)

    # Delete all steps
    await session_store.delete_steps(session_id, start_seq=0)


@router.get("/{session_id}/runs")
async def get_session_runs(
    session_id: str,
    limit: int = 20,
    offset: int = 0,
    session_store: SessionStore = Depends(get_session_store),
) -> PaginatedRuns:
    """Get runs for a session."""
    runs = await session_store.list_runs(
        session_id=session_id, limit=limit, offset=offset
    )

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
    offset: int = 0,
    session_store: SessionStore = Depends(get_session_store),
) -> PaginatedSteps:
    """Get steps for a session with pagination."""
    # Get total count
    total = await session_store.get_step_count(session_id)

    # Use start_seq to implement offset (sequence starts from 1)
    # offset 0 means start from sequence 1, offset 100 means start from sequence 101
    start_seq = offset + 1

    # Get steps with pagination
    steps = await session_store.get_steps(session_id, start_seq=start_seq, limit=limit)

    items = [
        StepResponse(
            id=step.id,
            session_id=step.session_id,
            sequence=step.sequence,
            role=step.role.value,
            content=step.content,
            reasoning_content=step.reasoning_content,
            tool_calls=step.tool_calls,
            name=step.name,
            tool_call_id=step.tool_call_id,
            created_at=step.created_at.isoformat() if step.created_at else "",
            run_id=step.run_id,
            parent_run_id=step.parent_run_id,
            runnable_id=step.runnable_id,
            runnable_type=step.runnable_type,
            depth=step.depth,
            metrics=step.metrics.model_dump(exclude_none=True) if step.metrics else None,
        ).model_dump(exclude_none=True)
        for step in steps
    ]

    return PaginatedSteps(total=total, items=items, limit=limit, offset=offset)


# Request Models for Fork/Retry
class ForkRequest(BaseModel):
    """Request to fork a session at a specific step."""

    sequence: int
    content: str | None = None  # Optional modified content for assistant step
    tool_calls: list[dict] | None = (
        None  # Optional modified tool_calls for assistant step
    )


class ForkResponse(BaseModel):
    """Response from fork operation."""

    new_session_id: str
    copied_steps: int
    last_sequence: int
    pending_user_message: str | None = (
        None  # For user step fork, the message to put in input box
    )


@router.post("/{session_id}/fork")
async def fork_session_endpoint(
    session_id: str,
    request: ForkRequest,
    session_store: SessionStore = Depends(get_session_store),
) -> ForkResponse:
    """
    Fork a session at a specific step (assistant or user).

    For assistant steps:
        - Creates new session with all steps up to and including the target
        - Can optionally modify content and/or tool_calls

    For user steps:
        - Creates new session with steps BEFORE the user step
        - Returns the user message in pending_user_message for the input box
    """
    # Validate session exists
    steps = await session_store.get_steps(session_id, limit=1)
    if not steps:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Validate sequence exists
    all_steps = await session_store.get_steps(session_id, end_seq=request.sequence)
    if not all_steps:
        raise HTTPException(
            status_code=400, detail=f"No steps found up to sequence {request.sequence}"
        )

    target_step = all_steps[-1]

    # Only assistant and user steps can be forked
    if target_step.role.value not in ("assistant", "user"):
        raise HTTPException(
            status_code=400,
            detail=f"Can only fork assistant or user steps, got: {target_step.role.value}",
        )

    try:
        # Perform fork
        new_session_id, last_sequence, pending_user_message = await fork_session(
            original_session_id=session_id,
            sequence=request.sequence,
            session_store=session_store,
            modified_content=request.content,
            modified_tool_calls=request.tool_calls,
        )

        return ForkResponse(
            new_session_id=new_session_id,
            copied_steps=len(all_steps) - (1 if pending_user_message else 0),
            last_sequence=last_sequence,
            pending_user_message=pending_user_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Resume Session
# ============================================================================


class ResumeRequest(BaseModel):
    """Request to resume a session."""

    runnable_id: str | None = (
        None  # Optional - auto-inferred from Steps if not provided
    )


@router.post("/{session_id}/resume")
async def resume_session_endpoint(
    session_id: str,
    request: ResumeRequest = ResumeRequest(),
    session_store: SessionStore = Depends(get_session_store),
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """
    Resume a session.

    Automatically infers runnable_id from Steps if not provided.
    Continues from pending tool_calls.

    Args:
        session_id: Session ID to resume
        request: Optional runnable_id (auto-inferred if not provided)

    Returns SSE stream of step events.
    """
    # Validate session exists
    steps = await session_store.get_steps(session_id, limit=1)
    if not steps:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Create ResumeExecutor
    executor = ResumeExecutor(store=session_store, config_system=config_sys)

    # Resume execution via SSE stream
    async def event_generator():
        wire = Wire()

        async def _run():
            try:
                await executor.resume_session(
                    session_id=session_id,
                    runnable_id=request.runnable_id,
                    wire=wire,
                )
            finally:
                await wire.close()

        task = asyncio.create_task(_run())

        try:
            async for event in wire.read():
                yield {
                    "event": event.type.value,
                    "data": event.model_dump_json(),
                }
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
        finally:
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
