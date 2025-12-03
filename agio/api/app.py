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

    # Initialize ConfigSystem
    from agio.config import get_config_system

    config_dir = os.getenv("AGIO_CONFIG_DIR", "./configs")

    try:
        config_sys = get_config_system()
        await config_sys.load_from_directory(config_dir)
        await config_sys.build_all()

        logger.info(
            "agio_api_initialized",
            config_dir=config_dir,
            components=len(config_sys.list_components()),
        )

        # Initialize LLM call tracker
        from agio.observability.tracker import get_tracker

        tracker = get_tracker()
        await tracker.initialize()
        logger.info("llm_tracker_initialized")

    except Exception as e:
        logger.error("agio_api_init_failed", error=str(e), exc_info=True)
        raise

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
