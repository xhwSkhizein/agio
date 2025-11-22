"""
Common Pydantic schemas for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Generic, TypeVar
from datetime import datetime

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response."""
    
    total: int
    items: list[T]
    limit: int = 20
    offset: int = 0
    
    @property
    def has_more(self) -> bool:
        return self.offset + self.limit < self.total


class ErrorResponse(BaseModel):
    """Error response."""
    
    error: dict[str, str]


class SuccessResponse(BaseModel):
    """Success response."""
    
    success: bool = True
    message: str
