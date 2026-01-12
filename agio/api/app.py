"""
FastAPI application for Agio Control Plane API.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agio.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    logger.info("agio_api_starting")

    # Ensure AgioApp is initialized and attached to state
    from agio.api.agio_app import AgioApp
    
    if not hasattr(app.state, "agio_app"):
        app.state.agio_app = AgioApp()

    # Manual Component Registration (Replacing ConfigSystem)
    try:
        from agio.api.setup import initialize_components
        await initialize_components(app.state.agio_app)

    except Exception as e:
        logger.error("agio_api_manual_init_failed", error=str(e), exc_info=True)
        # We don't raise here to allow API to start even if init fails
        pass

    yield

    logger.info("agio_api_shutdown")


def create_app() -> FastAPI:
    """
    Create FastAPI application with Agio Control Plane API.

    Returns:
        Configured FastAPI application
    """
    from .router import create_router

    app = FastAPI(
        title="Agio Control Plane API",
        description="RESTful API for managing agents, configurations, and system data.",
        version="0.1.0",
        docs_url="/agio/docs",
        redoc_url="/agio/redoc",
        openapi_url="/agio/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include main router
    app.include_router(create_router())

    return app


app = create_app()
