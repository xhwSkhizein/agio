"""
Global PermissionManager factory for dependency injection.

This module provides a singleton PermissionManager instance that is shared
across all Agents in the system. It is created lazily on first access.
"""

from agio.runtime.permission.manager import PermissionManager
from agio.utils.logging import get_logger

logger = get_logger(__name__)

_permission_manager: PermissionManager | None = None


def get_permission_manager() -> PermissionManager:
    """
    Get global PermissionManager singleton.

    This is called by ConfigSystem when building Agents with enable_permission=True.
    The PermissionManager is shared across all Agents in the system.

    Dependencies are lazily resolved from agio.api.deps to avoid circular imports.

    Returns:
        PermissionManager: Global singleton instance
    """
    global _permission_manager

    if _permission_manager is None:
        from agio.api.deps import (
            get_config_sys,
            get_consent_store,
            get_consent_waiter,
            get_permission_service,
        )

        logger.info("initializing_global_permission_manager")

        _permission_manager = PermissionManager(
            consent_store=get_consent_store(),
            consent_waiter=get_consent_waiter(),
            permission_service=get_permission_service(),
            config_system=get_config_sys(),
            cache_ttl=300,
            cache_size=1000,
        )

    return _permission_manager


def reset_permission_manager() -> None:
    """
    Reset global PermissionManager singleton.

    This is primarily used for testing to ensure a clean state.
    """
    global _permission_manager
    _permission_manager = None
    logger.debug("permission_manager_reset")


__all__ = ["get_permission_manager", "reset_permission_manager"]
