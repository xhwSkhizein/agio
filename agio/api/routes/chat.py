"""
Chat routes with SSE streaming support.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.agent import Agent
from agio.api.deps import get_config_sys
from agio.config import ConfigSystem
from agio.domain import StepEventType

router = APIRouter(prefix="/chat")


# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    stream: bool = True


class ChatResponse(BaseModel):
    run_id: str
    session_id: str
    response: str
    metrics: dict = {}


@router.post("/{agent_name}")
async def chat(
    agent_name: str,
    request: ChatRequest,
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """Chat with an agent."""
    # Get agent instance
    try:
        agent = config_sys.get(agent_name)
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found: {e}"
        )

    # Stream or non-stream
    if request.stream:
        return EventSourceResponse(
            stream_chat_events(
                agent, request.message, request.user_id, request.session_id
            ),
            sep="\n",  # Use LF instead of CRLF for SSE line separator
        )
    else:
        return await chat_non_streaming(
            agent, request.message, request.user_id, request.session_id
        )


async def stream_chat_events(
    agent: Agent, message: str, user_id: str | None, session_id: str | None
):
    """Stream chat events as SSE."""
    try:
        async for event in agent.arun_stream(
            query=message, user_id=user_id, session_id=session_id
        ):
            # Convert StepEvent to SSE format, excluding None values for cleaner output
            event_dict = event.model_dump(mode="json", exclude_none=True)
            event_type = event_dict.pop("type", "message")

            yield {"event": event_type, "data": json.dumps(event_dict)}

    except Exception as e:
        yield {"event": "error", "data": json.dumps({"error": str(e)})}


async def chat_non_streaming(
    agent: Agent, message: str, user_id: str | None, session_id: str | None
) -> ChatResponse:
    """Non-streaming chat."""
    response_content = ""
    run_id = None
    metrics = {}

    async for event in agent.arun_stream(
        query=message, user_id=user_id, session_id=session_id
    ):
        if event.type == StepEventType.RUN_STARTED:
            run_id = event.run_id

        elif event.type == StepEventType.STEP_DELTA:
            if event.delta and event.delta.content:
                response_content += event.delta.content

        elif event.type == StepEventType.RUN_COMPLETED:
            if event.data and "metrics" in event.data:
                metrics = event.data["metrics"]

    return ChatResponse(
        run_id=run_id or "unknown",
        session_id=session_id or "unknown",
        response=response_content,
        metrics=metrics,
    )
