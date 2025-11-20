import inspect
import json
from typing import Any, Callable, get_type_hints
from pydantic import BaseModel, create_model

from agio.tools.base import Tool

class FunctionTool(Tool):
    def __init__(self, func: Callable, name: str | None = None, description: str | None = None):
        self.func = func
        self.name = name or func.__name__
        self.description = description or func.__doc__ or ""
        self.args_schema = self._create_args_schema(func)

    def _create_args_schema(self, func: Callable) -> type[BaseModel]:
        """Dynamically create a Pydantic model from function signature."""
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        fields = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self" or param_name == "cls":
                continue
                
            annotation = type_hints.get(param_name, Any)
            default = param.default
            
            if default == inspect.Parameter.empty:
                fields[param_name] = (annotation, ...)
            else:
                fields[param_name] = (annotation, default)
                
        return create_model(f"{self.name}Args", **fields)

    async def execute(self, **kwargs) -> Any:
        if inspect.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        return self.func(**kwargs)

    def to_openai_schema(self) -> dict:
        if not self.args_schema:
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {"type": "object", "properties": {}},
                }
            }

        # Get JSON Schema from Pydantic
        schema = self.args_schema.model_json_schema()
        
        # Clean up top-level title (optional, but cleaner)
        schema.pop("title", None)
        
        # IMPORTANT: Do NOT remove $defs if they are used!
        # Only remove if you are sure they are not needed, or better yet, let them be.
        # OpenAI supports $defs in function parameters.
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            }
        }
