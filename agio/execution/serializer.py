"""
State serializer for converting Python objects to/from JSON.
"""

import json
from typing import Any
from datetime import datetime
from pydantic import BaseModel


class StateSerializer:
    """
    State Serializer.
    
    Responsibilities:
    1. Serialize Python objects to JSON
    2. Handle special types (datetime, Pydantic models, etc.)
    3. Compress large data
    """
    
    @staticmethod
    def serialize(obj: Any) -> str:
        """Serialize object to JSON string."""
        return json.dumps(
            obj,
            default=StateSerializer._json_encoder,
            ensure_ascii=False,
            indent=None  # Compact format
        )
    
    @staticmethod
    def deserialize(data: str, target_type: type = dict) -> Any:
        """Deserialize JSON string."""
        obj = json.loads(data)
        
        # If target type is Pydantic model, use model_validate
        if isinstance(target_type, type) and issubclass(target_type, BaseModel):
            return target_type.model_validate(obj)
        
        return obj
    
    @staticmethod
    def _json_encoder(obj: Any) -> Any:
        """Custom JSON encoder."""
        
        # Pydantic model
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode='json')
        
        # datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # Other types
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class MessageSerializer:
    """
    Message Serializer.
    
    Specialized for handling Message objects.
    """
    
    @staticmethod
    def serialize_messages(messages: list) -> list[dict]:
        """Serialize message list."""
        result = []
        for msg in messages:
            if isinstance(msg, BaseModel):
                result.append(msg.model_dump(mode='json', exclude_none=True))
            elif isinstance(msg, dict):
                result.append(msg)
            else:
                raise TypeError(f"Unsupported message type: {type(msg)}")
        return result
    
    @staticmethod
    def deserialize_messages(data: list[dict]) -> list[dict]:
        """Deserialize message list (returns dict format for flexibility)."""
        return data
