"""
API dependency injection.

Provides simplified dependency injection for the API layer.
Most dependencies are obtained from AgioApp instance.
"""

from typing import TYPE_CHECKING

from fastapi import Request

from agio.runtime.permission import (
    ConsentStore,
    ConsentWaiter,
    PermissionManager,
    PermissionService,
)
from agio.storage.session import SessionStore
from agio.storage.trace.store import TraceStore
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.api.agio_app import AgioApp

logger = get_logger(__name__)


def get_agio_app(request: Request) -> "AgioApp":
    """Get AgioApp from request state."""
    return request.app.state.agio_app


def get_session_store(request: Request) -> SessionStore:
    """Get SessionStore from AgioApp."""
    agio_app = get_agio_app(request)
    return agio_app.session_store


def get_trace_store(request: Request) -> TraceStore | None:
    """Get TraceStore from AgioApp."""
    agio_app = get_agio_app(request)
    return agio_app.trace_store


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


def get_consent_store(request: Request) -> "ConsentStore":
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

    session_store = get_session_store(request)

    # Try to reuse MongoDB connection from MongoSessionStore
    if isinstance(session_store, MongoSessionStore):
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


def get_permission_manager(request: Request) -> "PermissionManager":
    """Get global PermissionManager instance"""
    global _permission_manager
    if _permission_manager is None:
        from agio.runtime.permission import PermissionManager

        consent_store = get_consent_store(request)
        consent_waiter = get_consent_waiter()
        permission_service = get_permission_service()

        _permission_manager = PermissionManager(
            consent_store=consent_store,
            consent_waiter=consent_waiter,
            permission_service=permission_service,
            cache_ttl=300,
            cache_size=1000,
        )
    return _permission_manager
