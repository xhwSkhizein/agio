"""
Metrics API endpoints for querying agent and system metrics.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agio.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/metrics")


# Response Models
class AgentMetrics(BaseModel):
    agent_id: str
    total_runs: int
    success_rate: float
    avg_duration: float
    total_tokens: int
    avg_tokens_per_run: float


class SystemMetrics(BaseModel):
    total_agents: int
    total_runs: int
    active_runs: int
    total_tokens_today: int
    avg_response_time: float


@router.get("/agents/{agent_id}", response_model=AgentMetrics)
async def get_agent_metrics(
    agent_id: str,
    start_time: datetime | None = Query(None, description="Start time for metrics"),
    end_time: datetime | None = Query(None, description="End time for metrics"),
) -> AgentMetrics:
    """
    Get metrics for a specific agent.

    **Path Parameters:**
    - `agent_id`: Agent identifier

    **Query Parameters:**
    - `start_time`: Optional start time (ISO format)
    - `end_time`: Optional end time (ISO format)

    **Returns:** Aggregated metrics for the agent
    """
    try:
        # TODO: Implement with metrics aggregation from repository
        # For now, return mock data

        logger.info("agent_metrics_requested", agent_id=agent_id)

        return AgentMetrics(
            agent_id=agent_id,
            total_runs=0,
            success_rate=0.0,
            avg_duration=0.0,
            total_tokens=0,
            avg_tokens_per_run=0.0,
        )

    except Exception as e:
        logger.error(
            "get_agent_metrics_failed", agent_id=agent_id, error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get agent metrics: {str(e)}"
        )


@router.get("/system", response_model=SystemMetrics)
async def get_system_metrics() -> SystemMetrics:
    """
    Get system-wide metrics.

    **Returns:** Aggregated system metrics
    """
    try:
        # TODO: Implement with metrics aggregation
        # For now, return mock data

        logger.info("system_metrics_requested")

        return SystemMetrics(
            total_agents=0,
            total_runs=0,
            active_runs=0,
            total_tokens_today=0,
            avg_response_time=0.0,
        )

    except Exception as e:
        logger.error("get_system_metrics_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get system metrics: {str(e)}"
        )
