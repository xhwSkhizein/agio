"""
Knowledge data routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agio.api.deps import get_config_sys
from agio.config import ConfigSystem
from agio.core.config import ComponentType

router = APIRouter(prefix="/knowledge")


# Response Models
class KnowledgeInfo(BaseModel):
    name: str
    type: str


class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: int = 5


class KnowledgeSearchResult(BaseModel):
    content: str
    score: float | None = None
    metadata: dict | None = None


# Routes
@router.get("")
async def list_knowledge(
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> list[KnowledgeInfo]:
    """List all Knowledge components."""
    configs = config_sys.list_configs(ComponentType.KNOWLEDGE)

    return [
        KnowledgeInfo(
            name=config_doc.get("config", {}).get("name"),
            type=config_doc.get("config", {}).get("provider", "unknown"),
        )
        for config_doc in configs
    ]


@router.get("/{name}")
async def get_knowledge_info(
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> KnowledgeInfo:
    """Get Knowledge component info."""
    config = config_sys.get_config(ComponentType.KNOWLEDGE, name)

    if not config:
        raise HTTPException(status_code=404, detail=f"Knowledge '{name}' not found")

    return KnowledgeInfo(
        name=name,
        type=config.get("provider", "unknown"),
    )


@router.post("/{name}/search")
async def search_knowledge(
    name: str,
    request: KnowledgeSearchRequest,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> list[KnowledgeSearchResult]:
    """Search knowledge base."""
    try:
        knowledge = config_sys.get(name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Knowledge '{name}' not found: {e}")

    results = await knowledge.search(query=request.query, limit=request.limit)

    # Handle different result formats
    if results and isinstance(results[0], str):
        return [KnowledgeSearchResult(content=r) for r in results]

    # If results have more structure
    return [
        KnowledgeSearchResult(
            content=r.get("content", str(r)) if isinstance(r, dict) else str(r),
            score=r.get("score") if isinstance(r, dict) else None,
            metadata=r.get("metadata") if isinstance(r, dict) else None,
        )
        for r in results
    ]
