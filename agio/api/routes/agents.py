"""
Agent API routes - unified API for Agent execution.

Provides endpoints for listing agents and running them.
Works with AgioApp for direct Agent registration.
"""

import json
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

if TYPE_CHECKING:
    from agio.api.agio_app import AgioApp

router = APIRouter(prefix="/agents")

CLEANUP_TIMEOUT_SECONDS = 5.0


def get_agio_app(request: Request) -> "AgioApp":
    """Get AgioApp from request state."""
    if not hasattr(request.app.state, "agio_app"):
        raise HTTPException(
            status_code=500,
            detail="AgioApp not configured. Use AgioApp.get_app() to create the FastAPI app.",
        )
    return request.app.state.agio_app


class RunRequest(BaseModel):
    """Request body for running an Agent."""

    query: str | None = None
    message: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    stream: bool = True


class AgentInfo(BaseModel):
    """Information about an Agent."""

    id: str
    name: str
    runnable_type: str = "agent"
    model: str | None = None
    tools: list[dict] = []
    system_prompt: str | None = None


class AgentListResponse(BaseModel):
    """Response for listing agents."""

    items: list[AgentInfo]
    total: int


@router.get("", response_model=AgentListResponse)
async def list_agents(
    agio_app: "AgioApp" = Depends(get_agio_app),
) -> AgentListResponse:
    """List all registered Agents."""
    agents = agio_app.list_agents()
    return AgentListResponse(
        items=[AgentInfo(**a) for a in agents],
        total=len(agents),
    )


@router.get("/{agent_id}")
async def get_agent_info(
    agent_id: str,
    agio_app: "AgioApp" = Depends(get_agio_app),
) -> dict[str, Any]:
    """Get information about a specific Agent."""
    agent = agio_app.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {
        "id": agent.id,
        "name": agent.id,
        "runnable_type": "agent",
        "max_steps": agent.max_steps,
        "has_session_store": agent.session_store is not None,
    }


@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: str,
    request: RunRequest,
    agio_app: "AgioApp" = Depends(get_agio_app),
):
    """Execute an Agent."""
    agent = agio_app.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    input_text = request.query or request.message or ""
    session_id = request.session_id or str(uuid4())

    async def execute_and_stream():
        try:
            async for event in agent.run_stream(
                input_text,
                session_id=session_id,
                user_id=request.user_id,
                trace_store=agio_app.trace_store,
            ):
                yield {"event": event.type.value, "data": event.model_dump_json()}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    if request.stream:
        return EventSourceResponse(execute_and_stream())
    else:
        events = []
        async for event in execute_and_stream():
            events.append(event)
        return {"events": events}
