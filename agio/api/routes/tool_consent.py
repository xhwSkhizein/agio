"""
Tool consent API routes.

Handles user consent decisions for tool execution.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agio.api.deps import (
    get_consent_store,
    get_consent_waiter,
    get_permission_manager,
)
from agio.runtime.permission import (
    ConsentDecision,
    ConsentStore,
    ConsentWaiter,
    PermissionManager,
)
from agio.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tool-consent")


class ToolConsentRequest(BaseModel):
    """Request body for tool consent"""

    tool_call_id: str
    decision: Literal["allow", "deny"]
    patterns: list[str] = []  # Required when decision=allow
    expires_at: datetime | None = None
    user_id: str | None = None


class ToolConsentResponse(BaseModel):
    """Response for tool consent"""

    success: bool
    tool_call_id: str
    message: str


@router.post("", response_model=ToolConsentResponse)
async def submit_tool_consent(
    request: ToolConsentRequest,
    consent_store: ConsentStore = Depends(get_consent_store),
    consent_waiter: ConsentWaiter = Depends(get_consent_waiter),
    permission_manager: PermissionManager = Depends(get_permission_manager),
):
    """
    Submit tool authorization decision.
    
    When user grants consent:
    1. Save consent record to ConsentStore
    2. Clear related cache
    3. Wake up waiting task
    
    When user denies consent:
    1. Wake up waiting task with deny decision
    """
    # Validate request
    if request.decision == "allow" and not request.patterns:
        raise HTTPException(
            status_code=400,
            detail="patterns required when decision=allow",
        )

    # Construct decision
    decision = ConsentDecision(
        decision=request.decision,
        patterns=request.patterns,
        expires_at=request.expires_at,
    )

    # Save consent record (if allowed)
    if request.decision == "allow" and request.user_id:
        try:
            # Extract tool_name from patterns (first pattern)
            tool_name = None
            if request.patterns:
                first_pattern = request.patterns[0]
                open_paren = first_pattern.find("(")
                if open_paren > 0:
                    tool_name = first_pattern[:open_paren]

            await consent_store.save_consent(
                user_id=request.user_id,
                tool_name=tool_name,
                patterns=request.patterns,
                expires_at=request.expires_at,
            )

            # Clear related cache
            await permission_manager._invalidate_cache(
                request.user_id, tool_name=None  # Clear all tools for user
            )

            logger.info(
                "consent_saved",
                tool_call_id=request.tool_call_id,
                user_id=request.user_id,
                pattern_count=len(request.patterns),
            )
        except Exception as e:
            logger.error(
                "save_consent_failed",
                tool_call_id=request.tool_call_id,
                user_id=request.user_id,
                error=str(e),
                exc_info=True,
            )
            # Continue to wake up task even if save fails

    # Wake up waiting task
    try:
        await consent_waiter.resolve(request.tool_call_id, decision)
    except Exception as e:
        logger.error(
            "consent_resolve_failed",
            tool_call_id=request.tool_call_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resolve consent: {e}",
        )

    return ToolConsentResponse(
        success=True,
        tool_call_id=request.tool_call_id,
        message="Consent saved and execution resumed",
    )


__all__ = ["router"]

