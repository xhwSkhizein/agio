"""
Agent routes for CRUD operations.
"""

from fastapi import APIRouter, HTTPException
from agio.registry import get_registry
from agio.api.schemas.agent import AgentResponse, AgentCreateRequest, AgentUpdateRequest
from agio.api.schemas.common import PaginatedResponse, SuccessResponse

router = APIRouter(prefix="/api/agents", tags=["Agents"])


@router.get("", response_model=PaginatedResponse[AgentResponse])
async def list_agents(
    limit: int = 20,
    offset: int = 0,
    tag: str | None = None
):
    """List all agents."""
    registry = get_registry()
    
    # Get all agent names
    from agio.registry import ComponentType
    agent_names = registry.list_by_type(ComponentType.AGENT)
    
    # Filter by tag if provided
    if tag:
        tag_agents = set(registry.list_by_tag(tag))
        agent_names = [name for name in agent_names if name in tag_agents]
    
    # Pagination
    total = len(agent_names)
    paginated_names = agent_names[offset:offset + limit]
    
    # Build responses
    items = []
    for name in paginated_names:
        config = registry.get_config(name)
        if config:
            items.append(AgentResponse(
                id=name,
                name=name,
                description=config.description,
                model=config.model,
                tools=config.tools,
                enabled=config.enabled,
                tags=config.tags
            ))
    
    return PaginatedResponse(
        total=total,
        items=items,
        limit=limit,
        offset=offset
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get agent by ID."""
    registry = get_registry()
    
    config = registry.get_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    return AgentResponse(
        id=agent_id,
        name=agent_id,
        description=config.description,
        model=config.model,
        tools=config.tools if hasattr(config, 'tools') else [],
        enabled=config.enabled,
        tags=config.tags
    )


@router.post("", response_model=SuccessResponse, status_code=201)
async def create_agent(request: AgentCreateRequest):
    """Create a new agent."""
    # TODO: Implement agent creation from API
    # This would involve creating a config and registering the agent
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.put("/{agent_id}", response_model=SuccessResponse)
async def update_agent(agent_id: str, request: AgentUpdateRequest):
    """Update an agent."""
    # TODO: Implement agent update
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str):
    """Delete an agent."""
    registry = get_registry()
    
    if not registry.exists(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    registry.unregister(agent_id)
