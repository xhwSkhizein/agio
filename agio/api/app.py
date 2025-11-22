"""
FastAPI application for Agio Agent framework.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create FastAPI application."""
    
    app = FastAPI(
        title="Agio API",
        description="Agent Framework API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    from .routes import agents, chat, runs, checkpoints, health, config, metrics
    
    app.include_router(agents.router)
    app.include_router(chat.router)
    app.include_router(runs.router)
    app.include_router(checkpoints.router)
    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(metrics.router)
    
    # Startup event
    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting Agio API...")
        
        # Initialize Dependency Container
        from .dependencies import DependencyContainer
        import os
        
        try:
            config_dir = os.getenv("AGIO_CONFIG_DIR", "./configs")
            
            container = DependencyContainer.get_instance()
            container.initialize(config_dir)
            
            # Store config manager in app state for backward compatibility
            app.state.config_manager = container.config_manager
            
            # Log initialization success
            logger.info("✓ Dependency container initialized successfully")
            logger.info(f"✓ Repository: {type(container.repository).__name__}")
                    
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise e
    
    return app


app = create_app()
