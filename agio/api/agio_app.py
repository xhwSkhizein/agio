"""
AgioApp - Simplified API setup without ConfigSystem.

This module provides an AgioApp class for easily setting up the Control Panel API
with direct Agent registration, without requiring YAML configuration.

Usage:
    from agio import Agent, OpenAIModel
    from agio.api import AgioApp

    model = OpenAIModel(model_name="gpt-4o")
    agent = Agent(model=model, name="my_agent")

    app = AgioApp()
    app.register_agent(agent)

    # Get FastAPI app
    fastapi_app = app.get_app()
"""

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agio.storage.session import InMemorySessionStore
from agio.storage.trace.store import TraceStore
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.agent import Agent
    from agio.storage.session import SessionStore

logger = get_logger(__name__)


class AgioApp:
    """
    Simplified API setup for Agio Control Panel.

    Provides direct Agent registration without ConfigSystem.

    Example:
        app = AgioApp(session_store=store, trace_store=trace_store)
        app.register_agent(my_agent)
        fastapi_app = app.get_app()
    """

    def __init__(
        self,
        session_store: "SessionStore | None" = None,
        trace_store: "TraceStore | None" = None,
        title: str = "Agio Control Panel API",
        description: str = "RESTful API for agent execution and data querying.",
        version: str = "0.1.0",
    ):
        """
        Initialize AgioApp.

        Args:
            session_store: SessionStore for persistence (default: InMemorySessionStore)
            trace_store: TraceStore for trace persistence (optional)
            title: API title
            description: API description
            version: API version
        """
        self._agents: dict[str, "Agent"] = {}
        self.session_store: "SessionStore" = session_store or InMemorySessionStore()
        self.trace_store: "TraceStore | None" = trace_store
        self._title = title
        self._description = description
        self._version = version
        self._fastapi_app: FastAPI | None = None

    def register_agent(self, agent: "Agent") -> None:
        """
        Register an Agent instance.

        The Agent will be accessible via API endpoints using its id.

        Args:
            agent: Agent instance to register
        """
        if agent.id in self._agents:
            logger.warning(
                "agent_already_registered",
                agent_id=agent.id,
                message="Overwriting existing agent",
            )
        self._agents[agent.id] = agent
        logger.info("agent_registered", agent_id=agent.id)

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an Agent by id.

        Args:
            agent_id: Agent id to unregister

        Returns:
            True if agent was unregistered, False if not found
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info("agent_unregistered", agent_id=agent_id)
            return True
        return False

    def get_agent(self, agent_id: str) -> "Agent | None":
        """
        Get an Agent by id.

        Args:
            agent_id: Agent id

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(agent_id)

    def list_agents(self) -> list[dict]:
        """
        List all registered agents.

        Returns:
            List of agent info dicts with id and metadata
        """
        return [
            {
                "id": agent.id,
                "name": agent.id,
                "runnable_type": "agent",
                "model": agent.model.id if hasattr(agent.model, "id") else str(agent.model),
                "tools": [
                    {"name": t.name, "description": t.description} for t in agent.tools
                ],
                "system_prompt": agent.system_prompt,
            }
            for agent in self._agents.values()
        ]

    def get_app(self) -> FastAPI:
        """
        Get or create the FastAPI application.

        Returns:
            Configured FastAPI application with all routes
        """
        if self._fastapi_app is not None:
            return self._fastapi_app

        self._fastapi_app = self._create_app()
        return self._fastapi_app

    def _create_app(self) -> FastAPI:
        """Create and configure FastAPI application."""
        from agio.api.routes import agents as agents_routes
        from agio.api.routes import health, sessions, traces

        app = FastAPI(
            title=self._title,
            description=self._description,
            version=self._version,
            docs_url="/agio/docs",
            redoc_url="/agio/redoc",
            openapi_url="/agio/openapi.json",
        )

        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Store reference to self in app state for dependency injection
        app.state.agio_app = self

        # Include routers
        app.include_router(health.router, prefix="/agio", tags=["health"])
        app.include_router(agents_routes.router, prefix="/agio", tags=["agents"])
        app.include_router(sessions.router, prefix="/agio", tags=["sessions"])
        app.include_router(traces.router, prefix="/agio", tags=["traces"])

        logger.info(
            "agio_app_created",
            agents_count=len(self._agents),
            has_session_store=self.session_store is not None,
            has_trace_store=self.trace_store is not None,
        )

        return app


__all__ = ["AgioApp"]
