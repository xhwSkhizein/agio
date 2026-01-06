"""
Configuration management routes.
"""

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from agio.api.deps import get_config_sys
from agio.config import ComponentType, ConfigSystem
from agio.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/config")


# Request/Response Models
class ConfigData(BaseModel):
    """Configuration data for create/update."""

    config: dict[str, Any]


class ConfigResponse(BaseModel):
    type: str
    name: str
    config: dict[str, Any]


class ComponentInfo(BaseModel):
    name: str
    type: str | None
    dependencies: list[str]
    created_at: str | None


class MessageResponse(BaseModel):
    message: str
    details: dict[str, Any] | None = None


# Routes
@router.get("")
async def list_all_configs(
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> dict[str, list[dict]]:
    """List all configurations grouped by type."""
    result = {}
    for comp_type in ComponentType:
        configs = config_sys.list_configs(comp_type)
        if configs:
            # list_configs already returns dict objects, not nested structures
            result[comp_type.value] = configs
    return result


@router.get("/{config_type}")
async def list_configs_by_type(
    config_type: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> list[dict]:
    """List configurations of a specific type."""
    try:
        comp_type = ComponentType(config_type)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid config type: {config_type}"
        )

    configs = config_sys.list_configs(comp_type)
    # list_configs already returns dict objects, not nested structures
    return configs


@router.get("/{config_type}/{name}")
async def get_config(
    config_type: str,
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
) -> dict:
    """Get a specific configuration."""
    try:
        comp_type = ComponentType(config_type)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid config type: {config_type}"
        )

    config = config_sys.get_config(comp_type, name)
    if not config:
        raise HTTPException(
            status_code=404, detail=f"Config '{config_type}/{name}' not found"
        )

    return config


@router.put("/{config_type}/{name}", response_model=MessageResponse)
async def upsert_config(
    config_type: str,
    name: str,
    data: ConfigData,
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """Create or update a configuration."""
    try:
        comp_type = ComponentType(config_type)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid config type: {config_type}"
        )

    # Ensure name and type are set
    config_data = data.config.copy()
    config_data["name"] = name
    config_data["type"] = config_type

    # Parse and save config
    try:
        config_class = config_sys.CONFIG_CLASSES.get(comp_type)
        if not config_class:
            raise HTTPException(
                status_code=400, detail=f"Unknown config type: {config_type}"
            )

        config = config_class(**config_data)
        await config_sys.save_config(config)

        return MessageResponse(message=f"Config '{config_type}/{name}' saved")
    except Exception as e:
        logger.exception(f"Failed to upsert config {config_type}/{name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{config_type}/{name}", response_model=MessageResponse)
async def delete_config(
    config_type: str,
    name: str,
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """Delete a configuration."""
    try:
        comp_type = ComponentType(config_type)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid config type: {config_type}"
        )

    # Check exists
    if not config_sys.get_config(comp_type, name):
        raise HTTPException(
            status_code=404, detail=f"Config '{config_type}/{name}' not found"
        )

    try:
        await config_sys.delete_config(comp_type, name)
        return MessageResponse(message=f"Config '{config_type}/{name}' deleted")
    except Exception as e:
        logger.exception(f"Failed to delete config {config_type}/{name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/components", response_model=list[ComponentInfo])
async def list_components(
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """List all built component instances."""
    components = config_sys.list_components()
    return [
        ComponentInfo(
            name=c["name"],
            type=c["type"],
            dependencies=c["dependencies"],
            created_at=c["created_at"]
        ) for c in components
    ]


@router.post("/components/{name}/rebuild", response_model=MessageResponse)
async def rebuild_component(
    name: str,
    component_type: str | None = Query(None, description="Component type for targeted rebuild"),
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """Rebuild a component and its dependents."""
    try:
        ctype = None
        if component_type:
            try:
                ctype = ComponentType(component_type)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid component type: {component_type}"
                )
        
        await config_sys.rebuild(name, ctype)
        return MessageResponse(message=f"Component '{name}' rebuilt")
    except Exception as e:
        logger.exception(f"Failed to rebuild component {name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reload", response_model=MessageResponse)
async def reload_configs(
    config_sys: ConfigSystem = Depends(get_config_sys),
):
    """Reload all configurations from disk."""
    # Priority: 1. Current system config_dir, 2. AGIO_CONFIG_DIR env, 3. Default examples/configs
    config_dir = config_sys.config_dir or os.getenv("AGIO_CONFIG_DIR", "examples/configs")

    try:
        stats = await config_sys.load_from_directory(config_dir)
        await config_sys.build_all()
        return MessageResponse(message="Configs reloaded", details=stats)
    except Exception as e:
        logger.exception(f"Failed to reload configs from {config_dir}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
