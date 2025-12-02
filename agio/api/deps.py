"""
API dependency injection.

Provides unified dependency injection for the API layer.
All dependencies are obtained through ConfigSystem.
"""

from typing import Any

from fastapi import Depends, HTTPException

from agio.config import ConfigSystem, get_config_system
from agio.core.config import ComponentType
from agio.storage.repository import AgentRunRepository


def get_config_sys() -> ConfigSystem:
    """Get global ConfigSystem instance."""
    return get_config_system()


# Singleton InMemoryRepository for fallback
_default_repository: AgentRunRepository | None = None


def get_repository(
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> AgentRunRepository:
    """
    Get Repository instance.

    Priority:
    1. Get from ConfigSystem if already built
    2. Fall back to singleton InMemoryRepository
    """
    global _default_repository
    
    # Try to get repository from config system
    repos = config_sys.list_configs(ComponentType.REPOSITORY)
    if repos:
        # Prefer mongodb_repo if available
        for repo_config in repos:
            name = repo_config.get("name")
            if name:
                try:
                    repo = config_sys.get_or_none(name)
                    if repo is not None:
                        return repo
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Failed to get repository '{name}': {e}"
                    )

    # Fallback: create singleton InMemoryRepository
    if _default_repository is None:
        from agio.storage.repository import InMemoryRepository
        _default_repository = InMemoryRepository()

    return _default_repository


def get_agent(
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> Any:
    """
    Get Agent instance by name.

    Raises:
        HTTPException: If agent not found
    """
    try:
        return config_sys.get(name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found: {e}")


def get_memory(
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> Any:
    """
    Get Memory instance by name.

    Raises:
        HTTPException: If memory not found
    """
    try:
        return config_sys.get(name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Memory '{name}' not found: {e}")


def get_knowledge(
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> Any:
    """
    Get Knowledge instance by name.

    Raises:
        HTTPException: If knowledge not found
    """
    try:
        return config_sys.get(name)
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Knowledge '{name}' not found: {e}"
        )
