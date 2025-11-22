"""
Chat routes with SSE streaming support.
"""

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
import json
from agio.registry import get_registry
from agio.api.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("")
async def chat(request: ChatRequest):
    """
    Chat with an agent.
    
    Supports both streaming (SSE) and non-streaming modes.
    """
    registry = get_registry()
    
    # Get agent
    agent = registry.get(request.agent_id)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{request.agent_id}' not found"
        )
    
    if request.stream:
        # Streaming response with SSE
        return EventSourceResponse(
            stream_chat_events(
                agent,
                request.message,
                request.user_id,
                request.session_id
            )
        )
    else:
        # Non-streaming response
        return await chat_non_streaming(
            agent,
            request.message,
            request.user_id,
            request.session_id
        )


async def stream_chat_events(
    agent,
    message: str,
    user_id: str | None,
    session_id: str | None
):
    """Stream chat events as SSE."""
    try:
        async for event in agent.arun_stream(
            query=message,
            user_id=user_id,
            session_id=session_id
        ):
            # Convert AgentEvent to SSE format
            yield {
                "event": event.type,
                "data": json.dumps(event.data)
            }
    except Exception as e:
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)})
        }


async def chat_non_streaming(
    agent,
    message: str,
    user_id: str | None,
    session_id: str | None
) -> ChatResponse:
    """Non-streaming chat."""
    response_content = ""
    run_id = None
    metrics = {}
    
    async for event in agent.arun_stream(
        query=message,
        user_id=user_id,
        session_id=session_id
    ):
        if event.type == "run_started":
            run_id = event.data.get("run_id")
        
        elif event.type == "content_delta":
            response_content += event.data.get("content", "")
        
        elif event.type == "run_completed":
            metrics = event.data.get("metrics", {})
    
    return ChatResponse(
        run_id=run_id or "unknown",
        response=response_content,
        metrics=metrics
    )
