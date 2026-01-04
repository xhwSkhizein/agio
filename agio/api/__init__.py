"""
Agio Control Plane API.

Provides RESTful API for managing agents, configurations, and system data.

Usage:
    # Mode 1: Standalone server
    from agio.api import start_server
    start_server(host="0.0.0.0", port=8900)

    # Mode 2: Integrate with existing FastAPI
    from fastapi import FastAPI
    from agio.api import create_router

    app = FastAPI()
    app.include_router(create_router())

    # Mode 3: Integrate with frontend
    from agio.api import create_app_with_frontend
    app = create_app_with_frontend()

    # Mode 4: Disable API
    # Set environment variable: AGIO_API_ENABLED=false
"""

import os

from .app import create_app
from .router import create_router
from .static import create_app_with_frontend, get_frontend_dist_path, mount_frontend


def start_server(
    host: str = "0.0.0.0",
    port: int = 8900,
    reload: bool = False,
    **kwargs,
):
    """Start standalone Agio API server.

    Args:
        host: Bind host
        port: Bind port
        reload: Enable auto-reload for development
        **kwargs: Additional uvicorn arguments
    """
    import uvicorn

    uvicorn.run(
        "agio.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
        **kwargs,
    )


def is_api_enabled() -> bool:
    """Check if API is enabled via environment variable."""
    return os.getenv("AGIO_API_ENABLED", "true").lower() != "false"


__all__ = [
    "create_app",
    "create_app_with_frontend",
    "create_router",
    "get_frontend_dist_path",
    "mount_frontend",
    "start_server",
    "is_api_enabled",
]
