import pytest
import json
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from agio.tools.local import FunctionTool

def simple_func(a: int, b: str = "default"):
    """A simple function."""
    return f"{a}-{b}"

def complex_func(items: List[str], meta: Dict[str, int], flag: Optional[bool] = None):
    """Complex types function."""
    return len(items)

class UserInfo(BaseModel):
    name: str
    age: int = Field(description="Age of user")

def nested_model_func(user: UserInfo, action: str):
    """Function with Pydantic model."""
    return f"{action} {user.name}"

@pytest.mark.asyncio
async def test_simple_func_schema():
    tool = FunctionTool(simple_func)
    schema = tool.to_openai_schema()
    
    assert schema["function"]["name"] == "simple_func"
    assert schema["function"]["description"] == "A simple function."
    
    params = schema["function"]["parameters"]
    assert params["type"] == "object"
    assert "a" in params["properties"]
    assert params["properties"]["a"]["type"] == "integer"
    assert "b" in params["properties"]
    assert params["properties"]["b"]["type"] == "string"
    assert "a" in params["required"]
    assert "b" not in params["required"]

@pytest.mark.asyncio
async def test_complex_func_schema():
    tool = FunctionTool(complex_func)
    schema = tool.to_openai_schema()
    
    params = schema["function"]["parameters"]
    assert params["properties"]["items"]["type"] == "array"
    assert params["properties"]["items"]["items"]["type"] == "string"
    assert params["properties"]["meta"]["type"] == "object"
    
    # Optional field should handle null or just not be required
    # Pydantic v2 handles Optional[bool] usually as "anyOf": [{"type": "boolean"}, {"type": "null"}]
    # or just boolean but not required.
    flag_prop = params["properties"]["flag"]
    assert "boolean" in str(flag_prop) or "null" in str(flag_prop)

@pytest.mark.asyncio
async def test_nested_model_schema():
    tool = FunctionTool(nested_model_func)
    schema = tool.to_openai_schema()
    
    params = schema["function"]["parameters"]
    
    # Check if $defs exists because UserInfo should be defined there
    assert "$defs" in params or "definitions" in params
    
    # Check reference
    assert "$ref" in str(params["properties"]["user"])
    
    # Ensure $defs contains UserInfo
    defs = params.get("$defs", params.get("definitions", {}))
    assert "UserInfo" in defs
    assert defs["UserInfo"]["properties"]["age"]["description"] == "Age of user"

@pytest.mark.asyncio
async def test_execution():
    tool = FunctionTool(simple_func)
    result = await tool.execute(a=10, b="test")
    assert result == "10-test"

    tool2 = FunctionTool(simple_func)
    # Test defaults
    result2 = await tool2.execute(a=5)
    assert result2 == "5-default"

