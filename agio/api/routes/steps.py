"""
Steps API endpoints.

Provides access to Steps for a session, including:
- List steps
- Get step details
- Retry from sequence
- Fork session
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agio.api.dependencies import get_repository
from agio.db.repository import AgentRunRepository
from agio.execution.retry import retry_from_sequence
from agio.execution.fork import fork_session
from agio.domain.step import Step

router = APIRouter(prefix="/sessions", tags=["steps"])


class StepListResponse(BaseModel):
    """Response for listing steps"""
    steps: list[Step]
    total: int
    session_id: str


class RetryRequest(BaseModel):
    """Request to retry from a sequence"""
    sequence: int


class ForkRequest(BaseModel):
    """Request to fork a session"""
    sequence: int


class ForkResponse(BaseModel):
    """Response for fork operation"""
    new_session_id: str
    original_session_id: str
    forked_at_sequence: int
    copied_steps: int


@router.get("/{session_id}/steps", response_model=StepListResponse)
async def get_steps(
    session_id: str,
    start_seq: Optional[int] = None,
    end_seq: Optional[int] = None,
    limit: int = 1000,
    repository: AgentRunRepository = Depends(get_repository)
):
    """
    Get steps for a session.
    
    Args:
        session_id: Session ID
        start_seq: Minimum sequence (inclusive), None = no lower bound
        end_seq: Maximum sequence (inclusive), None = no upper bound
        limit: Maximum number of steps to return
    
    Returns:
        StepListResponse with steps and metadata
    """
    try:
        steps = await repository.get_steps(
            session_id=session_id,
            start_seq=start_seq,
            end_seq=end_seq,
            limit=limit
        )
        
        total = await repository.get_step_count(session_id)
        
        return StepListResponse(
            steps=steps,
            total=total,
            session_id=session_id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/steps/{sequence}")
async def get_step_by_sequence(
    session_id: str,
    sequence: int,
    repository: AgentRunRepository = Depends(get_repository)
):
    """
    Get a specific step by sequence number.
    
    Args:
        session_id: Session ID
        sequence: Sequence number
    
    Returns:
        Step or 404
    """
    try:
        steps = await repository.get_steps(
            session_id=session_id,
            start_seq=sequence,
            end_seq=sequence,
            limit=1
        )
        
        if not steps:
            raise HTTPException(status_code=404, detail="Step not found")
        
        return steps[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/retry")
async def retry_from_sequence_endpoint(
    session_id: str,
    request: RetryRequest,
    repository: AgentRunRepository = Depends(get_repository),
    # runner would be injected via dependency
):
    """
    Retry from a specific sequence.
    
    This deletes all steps with sequence >= N and resumes execution.
    Returns a streaming response with StepEvents.
    
    Args:
        session_id: Session ID to retry
        request: Retry request with sequence number
    
    Returns:
        StreamingResponse with StepEvents
    """
    # TODO: Get runner from dependency injection
    # For now, return error
    raise HTTPException(
        status_code=501,
        detail="Retry endpoint requires runner integration - coming soon"
    )
    
    # Implementation would be:
    # async def event_generator():
    #     async for event in retry_from_sequence(
    #         session_id,
    #         request.sequence,
    #         repository,
    #         runner
    #     ):
    #         yield event.to_sse()
    #
    # return StreamingResponse(
    #     event_generator(),
    #     media_type="text/event-stream"
    # )


@router.post("/{session_id}/fork", response_model=ForkResponse)
async def fork_session_endpoint(
    session_id: str,
    request: ForkRequest,
    repository: AgentRunRepository = Depends(get_repository)
):
    """
    Fork a session at a specific sequence.
    
    This creates a new session with a copy of all steps up to and including
    the specified sequence.
    
    Args:
        session_id: Original session ID
        request: Fork request with sequence number
    
    Returns:
        ForkResponse with new session ID and metadata
    """
    try:
        # Get original steps count
        original_steps = await repository.get_steps(
            session_id,
            end_seq=request.sequence
        )
        
        if not original_steps:
            raise HTTPException(
                status_code=404,
                detail=f"No steps found up to sequence {request.sequence}"
            )
        
        # Fork the session
        new_session_id = await fork_session(
            session_id,
            request.sequence,
            repository
        )
        
        return ForkResponse(
            new_session_id=new_session_id,
            original_session_id=session_id,
            forked_at_sequence=request.sequence,
            copied_steps=len(original_steps)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}/steps")
async def delete_steps_from_sequence(
    session_id: str,
    start_seq: int,
    repository: AgentRunRepository = Depends(get_repository)
):
    """
    Delete steps from a specific sequence onwards.
    
    This is used internally by retry operations.
    
    Args:
        session_id: Session ID
        start_seq: Starting sequence (inclusive)
    
    Returns:
        Number of deleted steps
    """
    try:
        deleted_count = await repository.delete_steps(
            session_id,
            start_seq=start_seq
        )
        
        return {
            "deleted_count": deleted_count,
            "session_id": session_id,
            "start_seq": start_seq
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/context")
async def get_context_preview(
    session_id: str,
    repository: AgentRunRepository = Depends(get_repository)
):
    """
    Get a preview of the LLM context that would be built from steps.
    
    Useful for debugging and understanding what the LLM sees.
    
    Args:
        session_id: Session ID
    
    Returns:
        Context messages and summary
    """
    try:
        from agio.runners.step_context import (
            build_context_from_steps,
            get_context_summary
        )
        
        # Build context
        messages = await build_context_from_steps(session_id, repository)
        
        # Get summary
        summary = await get_context_summary(session_id, repository)
        
        return {
            "session_id": session_id,
            "messages": messages,
            "summary": summary
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
