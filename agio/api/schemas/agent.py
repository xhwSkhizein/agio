"""
Agent-related Pydantic schemas.
"""

from pydantic import BaseModel, Field
from datetime import datetime


class AgentResponse(BaseModel):
    """Agent response schema."""
    
    id: str
    name: str
    description: str | None = None
    model: str
    tools: list[str] = Field(default_factory=list)
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class AgentCreateRequest(BaseModel):
    """Agent creation request."""
    
    name: str
    description: str | None = None
    model: str
    tools: list[str] = Field(default_factory=list)
    system_prompt: str | None = None
    tags: list[str] = Field(default_factory=list)


class AgentUpdateRequest(BaseModel):
    """Agent update request."""
    
    description: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    system_prompt: str | None = None
    enabled: bool | None = None
    tags: list[str] | None = None
