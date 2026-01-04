"""
API dependency injection.

Provides unified dependency injection for the API layer.
All dependencies are obtained through ConfigSystem.
"""

from typing import Any

from fastapi import Depends, HTTPException

from agio.config import ComponentType, ConfigSystem, get_config_system
from agio.runtime.permission import (
    ConsentStore,
    ConsentWaiter,
    PermissionManager,
    PermissionService,
)
from agio.storage.session import SessionStore
from agio.storage.trace.store import TraceStore
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
        from agio.storage.session import InMemorySessionStore

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
        raise HTTPException(status_code=404, detail=f"Knowledge '{name}' not found: {e}")


# Singleton InMemoryTraceStore for fallback
_default_trace_store: TraceStore | None = None


def get_trace_store(
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> TraceStore | None:
    """
    Get TraceStore instance from ConfigSystem.

    Priority:
    1. Get from ConfigSystem if already built
    2. Fall back to singleton in-memory TraceStore
    """
    global _default_trace_store

    # Try to get trace_store from config system
    stores = config_sys.list_configs(ComponentType.TRACE_STORE)
    if stores:
        for store_config in stores:
            name = store_config.get("name")
            if name:
                try:
                    store = config_sys.get_or_none(name)
                    if store is not None:
                        return store
                except Exception as e:
                    logger.warning("get_trace_store_failed", name=name, error=str(e))

    # Fallback: create singleton in-memory TraceStore
    if _default_trace_store is None:
        from agio.storage.trace.store import TraceStore

        _default_trace_store = TraceStore()

    return _default_trace_store


# Singleton ConsentWaiter
_consent_waiter: "ConsentWaiter | None" = None


def get_consent_waiter() -> "ConsentWaiter":
    """Get global ConsentWaiter instance"""
    global _consent_waiter
    if _consent_waiter is None:
        from agio.runtime.permission import ConsentWaiter

        _consent_waiter = ConsentWaiter(default_timeout=300.0)
    return _consent_waiter


# Singleton PermissionService
_permission_service: "PermissionService | None" = None


def get_permission_service() -> "PermissionService":
    """Get global PermissionService instance"""
    global _permission_service
    if _permission_service is None:
        from agio.runtime.permission import PermissionService

        _permission_service = PermissionService()
    return _permission_service


# Singleton ConsentStore
_consent_store: "ConsentStore | None" = None


def get_consent_store(
    config_sys: ConfigSystem = Depends(get_config_sys),
    session_store: SessionStore = Depends(get_session_store),
) -> "ConsentStore":
    """
    Get ConsentStore instance.

    Reuses SessionStore's MongoDB connection if available.
    Falls back to InMemoryConsentStore.
    """
    global _consent_store
    if _consent_store is not None:
        return _consent_store

    from agio.runtime.permission import InMemoryConsentStore, MongoConsentStore
    from agio.storage.session import MongoSessionStore

    # Try to reuse MongoDB connection from MongoSessionStore
    if isinstance(session_store, MongoSessionStore):
        # Reuse MongoDB connection (connection will be established on first use)
        # Note: client may be None initially, but will be set when _ensure_connection is called
        _consent_store = MongoConsentStore(
            client=session_store.client, db_name=session_store.db_name
        )
    else:
        # Fallback to in-memory
        _consent_store = InMemoryConsentStore()
        logger.info("using_inmemory_consent_store")

    return _consent_store


# Singleton PermissionManager
_permission_manager: "PermissionManager | None" = None


def get_permission_manager(
    consent_store: "ConsentStore" = Depends(get_consent_store),
    consent_waiter: "ConsentWaiter" = Depends(get_consent_waiter),
    permission_service: "PermissionService" = Depends(get_permission_service),
) -> "PermissionManager":
    """Get global PermissionManager instance"""
    global _permission_manager
    if _permission_manager is None:
        from agio.runtime.permission import PermissionManager

        _permission_manager = PermissionManager(
            consent_store=consent_store,
            consent_waiter=consent_waiter,
            permission_service=permission_service,
            cache_ttl=300,
            cache_size=1000,
        )
    return _permission_manager
