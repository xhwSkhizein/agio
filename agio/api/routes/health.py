"""
Health check routes.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

if TYPE_CHECKING:
    from agio.api.agio_app import AgioApp

router = APIRouter(prefix="/health")


def get_agio_app(request: Request) -> "AgioApp":
    """Get AgioApp from request state."""
    return request.app.state.agio_app


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class ReadyResponse(BaseModel):
    ready: bool
    agents: int


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now().isoformat(),
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready_check(
    agio_app: "AgioApp" = Depends(get_agio_app),
) -> ReadyResponse:
    """Readiness check - verifies system is fully initialized."""
    agents = agio_app.list_agents()

    return ReadyResponse(
        ready=len(agents) > 0,
        agents=len(agents),
    )
