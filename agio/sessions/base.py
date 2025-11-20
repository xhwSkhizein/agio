from typing import Optional
from pydantic import BaseModel, Field
from agio.memory.base import Memory

class AgentSession(BaseModel):
    """
    Represents the state of a conversation session.
    """
    session_id: str
    user_id: Optional[str] = None
    # Memory is referenced here, but managed by the Runner/Agent configuration
    # We might want to store session-specific ephemeral state here too.
    
    # For now, it's a simple data holder.

