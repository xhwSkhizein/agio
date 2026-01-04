"""
Permission system for tool execution.

This module provides a unified permission management system for controlling
tool execution based on user consent and authorization policies.
"""

from agio.runtime.permission.consent_store import (
    ConsentStore,
    InMemoryConsentStore,
    MongoConsentStore,
)
from agio.runtime.permission.consent_waiter import ConsentDecision, ConsentWaiter
from agio.runtime.permission.manager import ConsentResult, PermissionManager
from agio.runtime.permission.service import PermissionDecision, PermissionService

__all__ = [
    "PermissionManager",
    "ConsentResult",
    "ConsentStore",
    "InMemoryConsentStore",
    "MongoConsentStore",
    "ConsentWaiter",
    "ConsentDecision",
    "PermissionService",
    "PermissionDecision",
]
