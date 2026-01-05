"""
Main API router - aggregates all sub-routers.
"""

from fastapi import APIRouter


def create_router(prefix: str = "/agio") -> APIRouter:
    """
    Create the main Agio API router.

    Args:
        prefix: URL prefix for all routes (default: "/agio")

    Returns:
        Configured APIRouter with all sub-routers included
    """
    from agio.api.routes import (
        agents,
        config,
        health,
        metrics,
        runnables,
        sessions,
        tool_consent,
        traces,
    )

    router = APIRouter(prefix=prefix)

    # Health check
    router.include_router(health.router, tags=["Health"])

    # Configuration management
    router.include_router(config.router, tags=["Config"])

    # Agent management
    router.include_router(agents.router, tags=["Agents"])

    # Runnable API (unified Agent)
    router.include_router(runnables.router, tags=["Runnables"])

    # Session management
    router.include_router(sessions.router, tags=["Sessions"])

    # Metrics
    router.include_router(metrics.router, tags=["Metrics"])

    # Tool Consent
    router.include_router(tool_consent.router, tags=["Tool Consent"])

    # Traces (Observability)
    router.include_router(traces.router, tags=["Observability"])

    return router
