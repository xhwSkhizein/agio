"""
Memory data routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agio.api.deps import get_config_sys
from agio.config import ConfigSystem
from agio.config import ComponentType

router = APIRouter(prefix="/memory")


# Response Models
class MemoryInfo(BaseModel):
    name: str
    type: str
    has_history: bool
    has_semantic: bool


class MemorySearchRequest(BaseModel):
    query: str
    user_id: str | None = None
    limit: int = 10


class MemorySearchResult(BaseModel):
    content: str
    category: str | None = None
    score: float | None = None


# Routes
@router.get("")
async def list_memories(
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> list[MemoryInfo]:
    """List all Memory components."""
    configs = config_sys.list_configs(ComponentType.MEMORY)

    result = []
    for config_doc in configs:
        config = config_doc.get("config", {})
        name = config.get("name")

        # Try to get instance to check capabilities
        try:
            instance = config_sys.get_or_none(name)
            has_history = hasattr(instance, "history") and instance.history is not None
            has_semantic = hasattr(instance, "semantic") and instance.semantic is not None
        except Exception:
            has_history = False
            has_semantic = False

        result.append(
            MemoryInfo(
                name=name,
                type=config.get("provider", "unknown"),
                has_history=has_history,
                has_semantic=has_semantic,
            )
        )

    return result


@router.get("/{name}")
async def get_memory_info(
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> MemoryInfo:
    """Get Memory component info."""
    config = config_sys.get_config(ComponentType.MEMORY, name)

    if not config:
        raise HTTPException(status_code=404, detail=f"Memory '{name}' not found")

    try:
        instance = config_sys.get_or_none(name)
        has_history = hasattr(instance, "history") and instance.history is not None
        has_semantic = hasattr(instance, "semantic") and instance.semantic is not None
    except Exception:
        has_history = False
        has_semantic = False

    return MemoryInfo(
        name=name,
        type=config.get("provider", "unknown"),
        has_history=has_history,
        has_semantic=has_semantic,
    )


@router.post("/{name}/search")
async def search_memory(
    name: str,
    request: MemorySearchRequest,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> list[MemorySearchResult]:
    """Search memory for relevant content."""
    try:
        memory = config_sys.get(name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Memory '{name}' not found: {e}")

    if not hasattr(memory, "semantic") or memory.semantic is None:
        raise HTTPException(status_code=400, detail=f"Memory '{name}' does not support semantic search")

    user_id = request.user_id or "default"

    results = await memory.semantic.recall(
        user_id=user_id,
        query=request.query,
        limit=request.limit,
    )

    return [
        MemorySearchResult(
            content=r.content,
            category=r.category.value if r.category else None,
        )
        for r in results
    ]


@router.get("/{name}/history/{session_id}")
async def get_memory_history(
    name: str,
    session_id: str,
    limit: int = 50,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> list[dict]:
    """Get chat history from memory."""
    try:
        memory = config_sys.get(name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Memory '{name}' not found: {e}")

    if not hasattr(memory, "history") or memory.history is None:
        raise HTTPException(status_code=400, detail=f"Memory '{name}' does not support history")

    steps = await memory.history.get_recent_history(session_id, limit=limit)

    return [
        {
            "id": step.id,
            "role": step.role.value,
            "content": step.content,
            "sequence": step.sequence,
        }
        for step in steps
    ]
