"""
Chat-related Pydantic schemas.
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request schema."""
    
    agent_id: str = Field(description="Agent ID")
    message: str = Field(description="User message")
    user_id: str | None = Field(default=None, description="User ID")
    session_id: str | None = Field(default=None, description="Session ID")
    stream: bool = Field(default=True, description="Whether to stream response")
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "customer_support",
                "message": "How do I reset my password?",
                "user_id": "user_123",
                "stream": True
            }
        }


class ChatResponse(BaseModel):
    """Chat response (non-streaming)."""
    
    run_id: str
    response: str
    metrics: dict
