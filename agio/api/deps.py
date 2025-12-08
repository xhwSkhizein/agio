"""
API dependency injection.

Provides unified dependency injection for the API layer.
All dependencies are obtained through ConfigSystem.
"""

from typing import Any

from fastapi import Depends, HTTPException

from agio.config import ComponentType, ConfigSystem, get_config_system
from agio.providers.storage import SessionStore
from agio.utils.logging import get_logger

logger = get_logger(__name__)


def get_config_sys() -> ConfigSystem:
    """Get global ConfigSystem instance."""
    return get_config_system()


# Singleton InMemorySessionStore for fallback
_default_session_store: SessionStore | None = None


def get_session_store(
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> SessionStore:
    """
    Get SessionStore instance.

    Priority:
    1. Get from ConfigSystem if already built
    2. Fall back to singleton InMemorySessionStore
    """
    global _default_session_store
    
    # Try to get session_store from config system
    stores = config_sys.list_configs(ComponentType.SESSION_STORE)
    if stores:
        # Prefer mongodb_session_store if available
        for store_config in stores:
            name = store_config.get("name")
            if name:
                try:
                    store = config_sys.get_or_none(name)
                    if store is not None:
                        return store
                except Exception as e:
                    logger.warning("get_session_store_failed", name=name, error=str(e))

    # Fallback: create singleton InMemorySessionStore
    if _default_session_store is None:
        from agio.providers.storage import InMemorySessionStore
        _default_session_store = InMemorySessionStore()

    return _default_session_store


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
