"""
Health check routes.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agio.api.deps import get_config_sys
from agio.config import ConfigSystem

router = APIRouter(prefix="/health")


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class ReadyResponse(BaseModel):
    ready: bool
    components: int
    configs: int


@router.get("", response_model=HealthResponse)
async def health_check():
    """Basic health check."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now().isoformat(),
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready_check(config_sys: ConfigSystem = Depends(get_config_sys)):
    """Readiness check - verifies system is fully initialized."""
    components = config_sys.list_components()
    configs = config_sys.list_configs()

    return ReadyResponse(
        ready=len(components) > 0,
        components=len(components),
        configs=len(configs),
    )
