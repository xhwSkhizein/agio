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

    Example:
        # Integrate with existing FastAPI app
        from fastapi import FastAPI
        from agio.api import create_router

        app = FastAPI()
        app.include_router(create_router())

        # Custom prefix
        app.include_router(create_router(prefix="/admin/agio"))
    """
    from .routes import agents, chat, config, health, knowledge, llm_logs, memory, metrics, sessions

    router = APIRouter(prefix=prefix)

    # Health check
    router.include_router(health.router, tags=["Health"])

    # Configuration management
    router.include_router(config.router, tags=["Config"])

    # Agent management
    router.include_router(agents.router, tags=["Agents"])

    # Chat testing
    router.include_router(chat.router, tags=["Chat"])

    # Session management
    router.include_router(sessions.router, tags=["Sessions"])

    # Memory data
    router.include_router(memory.router, tags=["Memory"])

    # Knowledge data
    router.include_router(knowledge.router, tags=["Knowledge"])

    # Metrics
    router.include_router(metrics.router, tags=["Metrics"])

    # LLM Logs
    router.include_router(llm_logs.router, tags=["LLM Logs"])

    return router
