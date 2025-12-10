"""
Chat routes with SSE streaming support.

Wire-based Architecture:
- Wire is created at API entry point
- Events are streamed from wire.read()
- agent.run() writes events to wire and returns RunOutput
"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.agent import Agent
from agio.api.deps import get_config_sys
from agio.config import ConfigSystem
from agio.domain import StepEventType
from agio.runtime.wire import Wire
from agio.workflow.protocol import RunContext

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
            headers={
                # Disable keep-alive for SSE to release connection immediately after stream ends
                "Connection": "close",
                # Prevent proxy buffering
                "X-Accel-Buffering": "no",
            },
        )
    else:
        return await chat_non_streaming(
            agent, request.message, request.user_id, request.session_id
        )


async def stream_chat_events(
    agent: Agent, message: str, user_id: str | None, session_id: str | None
):
    """Stream chat events as SSE using Wire."""
    wire = Wire()
    context = RunContext(
        wire=wire,
        session_id=session_id,
        user_id=user_id,
    )

    async def _run():
        try:
            await agent.run(message, context=context)
        finally:
            await wire.close()

    task = asyncio.create_task(_run())

    try:
        async for event in wire.read():
            # Convert StepEvent to SSE format, excluding None values for cleaner output
            event_dict = event.model_dump(mode="json", exclude_none=True)
            event_type = event_dict.pop("type", "message")
            yield {"event": event_type, "data": json.dumps(event_dict)}

    except Exception as e:
        yield {"event": "error", "data": json.dumps({"error": str(e)})}
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def chat_non_streaming(
    agent: Agent, message: str, user_id: str | None, session_id: str | None
) -> ChatResponse:
    """Non-streaming chat using Wire."""
    wire = Wire()
    context = RunContext(
        wire=wire,
        session_id=session_id,
        user_id=user_id,
    )

    response_content = ""
    run_id = None
    metrics = {}

    async def _run():
        try:
            return await agent.run(message, context=context)
        finally:
            await wire.close()

    task = asyncio.create_task(_run())

    try:
        async for event in wire.read():
            if event.type == StepEventType.RUN_STARTED:
                run_id = event.run_id

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

    return ChatResponse(
        run_id=run_id or "unknown",
        session_id=session_id or "unknown",
        response=response_content,
        metrics=metrics,
    )
