"""
Agent management routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agio.api.deps import get_config_sys
from agio.config import ConfigSystem
from agio.config import ComponentType

router = APIRouter(prefix="/agents")


# Response Models
class AgentResponse(BaseModel):
    name: str
    model: str
    tools: list[str] = []
    memory: str | None = None
    knowledge: str | None = None
    system_prompt: str | None = None
    tags: list[str] = []


class AgentStatusResponse(BaseModel):
    name: str
    built: bool
    dependencies: list[str]
    created_at: str | None


class PaginatedAgents(BaseModel):
    total: int
    items: list[AgentResponse]
    limit: int
    offset: int


@router.get("", response_model=PaginatedAgents)
async def list_agents(
    limit: int = 20,
    offset: int = 0,
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """List all agents."""
    configs = config_sys.list_configs(ComponentType.AGENT)

    items = []
    for config_doc in configs:
        config = config_doc.get("config", {})
        items.append(
            AgentResponse(
                name=config.get("name"),
                model=config.get("model"),
                tools=config.get("tools", []),
                memory=config.get("memory"),
                knowledge=config.get("knowledge"),
                system_prompt=config.get("system_prompt"),
                tags=config.get("tags", []),
            )
        )

    total = len(items)
    paginated_items = items[offset : offset + limit]

    return PaginatedAgents(total=total, items=paginated_items, limit=limit, offset=offset)


@router.get("/{name}", response_model=AgentResponse)
async def get_agent(
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """Get agent configuration by name."""
    config = config_sys.get_config(ComponentType.AGENT, name)

    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    return AgentResponse(
        name=config.get("name"),
        model=config.get("model"),
        tools=config.get("tools", []),
        memory=config.get("memory"),
        knowledge=config.get("knowledge"),
        system_prompt=config.get("system_prompt"),
        tags=config.get("tags", []),
    )


@router.get("/{name}/status", response_model=AgentStatusResponse)
async def get_agent_status(
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """Get agent runtime status."""
    # Check config exists
    config = config_sys.get_config(ComponentType.AGENT, name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    # Get component info
    info = config_sys.get_component_info(name)

    return AgentStatusResponse(
        name=name,
        built=info is not None,
        dependencies=info.get("dependencies", []) if info else [],
        created_at=info.get("created_at") if info else None,
    )


# Note: Agent CRUD operations are handled via /config/agent/{name} routes
